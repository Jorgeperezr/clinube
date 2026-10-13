"""
Acceso del paciente a la app (GET/POST/DELETE /patients/{id}/app-access/).

Hasta ahora no había forma de enlazar una ficha con su cuenta de la app:
el paciente entraba con su código y se encontraba con «tu cuenta aún no
está enlazada» para siempre, porque `Patient.user` solo lo llenaban las
pruebas. Aquí lo hace la recepción, desde la ficha:

  · Activar: con el teléfono de la ficha, en E.164, se crea (o se
    reutiliza) la cuenta de paciente y se enlaza. Desde ese momento el
    paciente pide su código por WhatsApp con ese número y entra.
  · Quitar: se desenlaza y la cuenta se desactiva. El token que tuviera
    deja de valer en el acto (simplejwt rechaza usuarios inactivos).

Un mismo número da acceso a UNA sola ficha: la cuenta es por teléfono y
`User.phone` es único. Si ya entra con otra ficha (otro paciente, u otra
clínica), se dice en vez de moverla en silencio.

Si la plataforma manda el código por correo (Plataforma → Configuración),
lo que hace falta es el correo de la ficha, y vale la misma regla: cada
correo, una sola ficha (`User.email` también es único). El teléfono
entonces es opcional. Con WhatsApp, el correo se guarda igualmente en la
cuenta si está libre: así pasar de un canal a otro no obliga a volver a
activar a nadie.

Requiere la función «App del paciente» activa en la clínica.
"""

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.acceso_paciente import CORREO, canal_codigo, normalizar_correo
from apps.accounts.models import AuditLog, User
from apps.common.funcionalidades import activa
from apps.common.permisos_funcionalidad import RequiereFuncionalidad
from apps.common.permissions import HasRole
from apps.common.telefonos import normalizar_telefono
from apps.patients.models import Patient


def _estado(paciente):
    cuenta = paciente.user if paciente.user_id and paciente.user.is_active else None
    telefono = normalizar_telefono(paciente.phone)
    correo = normalizar_correo(paciente.email)
    return {
        "activo": cuenta is not None,
        "telefono": cuenta.phone if cuenta else telefono,
        # El de la ficha, normalizado: si no coincide con el de la cuenta,
        # el paciente cambió de número y hay que volver a activar.
        "telefono_ficha": telefono,
        "telefono_valido": bool(telefono),
        "correo": (cuenta.email or correo) if cuenta else correo,
        "correo_valido": bool(correo),
        # Por dónde le llega el código: el panel lo explica con esto.
        "canal": canal_codigo(),
        "ultimo_ingreso": cuenta.last_login if cuenta else None,
        "funcion_activa": activa(paciente.tenant, "app_paciente"),
    }


def _auditar(request, paciente, accion, **datos):
    AuditLog.objects.create(
        tenant=request.tenant, user=request.user, action=accion,
        entity_type="Patient", entity_id=str(paciente.id), metadata=datos,
    )


class AccesoAppView(APIView):
    permission_classes = [HasRole.for_roles("admin", "reception")]

    def _paciente(self, request, pk):
        return generics.get_object_or_404(
            Patient.objects.select_related("user", "tenant"), pk=pk, tenant=request.tenant,
        )

    def get(self, request, pk):
        return Response(_estado(self._paciente(request, pk)))

    def post(self, request, pk):
        if not RequiereFuncionalidad.para("app_paciente")().has_permission(request, self):
            return Response(
                {"detail": "La app del paciente no está activa en esta clínica. "
                           "Pídesela al administrador de la plataforma."},
                status=status.HTTP_403_FORBIDDEN)
        paciente = self._paciente(request, pk)
        telefono = normalizar_telefono(paciente.phone)
        correo = normalizar_correo(paciente.email)
        por_correo = canal_codigo() == CORREO
        if por_correo and not correo:
            return Response(
                {"detail": "La ficha no tiene un correo electrónico válido. Corrígelo en los "
                           "datos del paciente: es adonde le llegará el código para entrar."},
                status=status.HTTP_400_BAD_REQUEST)
        if not por_correo and not telefono:
            return Response(
                {"detail": "La ficha no tiene un teléfono móvil válido. Corrígelo en los "
                           "datos del paciente: es el número con el que entrará a la app."},
                status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            cuenta = None
            if telefono:
                cuenta = User.objects.select_for_update().filter(phone=telefono).first()
                if cuenta is not None and cuenta.role != User.Role.PATIENT:
                    if not por_correo:
                        return Response(
                            {"detail": "Ese teléfono es el de una persona del equipo. Cada número "
                                       "entra a una sola cuenta: usa otro para el paciente."},
                            status=status.HTTP_409_CONFLICT)
                    # Por correo el teléfono no hace falta: la cuenta va sin él.
                    cuenta, telefono = None, None
            if cuenta is None and por_correo:
                cuenta = User.objects.select_for_update().filter(email__iexact=correo).first()
                if cuenta is not None and cuenta.role != User.Role.PATIENT:
                    return Response(
                        {"detail": "Ese correo es el de una persona del equipo. Cada correo "
                                   "entra a una sola cuenta: usa otro para el paciente."},
                        status=status.HTTP_409_CONFLICT)
            if cuenta is None and por_correo and paciente.user_id:
                # La misma ficha, que ya tenía cuenta (con otro teléfono o sin él).
                cuenta = paciente.user
            otra = (Patient.objects.filter(user=cuenta).exclude(pk=paciente.pk).first()
                    if cuenta is not None else None)
            if otra is not None and otra.is_active:
                dato = "correo" if por_correo else "teléfono"
                return Response(
                    {"detail": f"Ese {dato} ya da acceso a la app a otra ficha (de otro "
                               "paciente o de otra clínica). Cada uno entra a una sola "
                               f"ficha: revisa el {dato} de las dos."},
                    status=status.HTTP_409_CONFLICT)
            if por_correo:
                ocupado = (User.objects.filter(email__iexact=correo)
                           .exclude(pk=getattr(cuenta, "pk", None)).exists())
                if ocupado:
                    return Response(
                        {"detail": "Ese correo ya da acceso a la app a otra ficha (de otro "
                                   "paciente o de otra clínica). Cada uno entra a una sola "
                                   "ficha: revisa el correo de las dos."},
                        status=status.HTTP_409_CONFLICT)
            if otra is not None:
                # La otra ficha está borrada: la cuenta queda libre.
                otra.user = None
                otra.save(update_fields=["user"])

            # Si la ficha ya tenía otra cuenta (cambió de teléfono), esa se
            # desactiva: el acceso va con la nueva.
            anterior = paciente.user if paciente.user_id and paciente.user_id != getattr(cuenta, "id", None) else None
            if anterior is not None:
                anterior.is_active = False
                anterior.save(update_fields=["is_active"])

            # El correo va en la cuenta si nadie más lo tiene: con él puede
            # entrar también cuando el código llegue por correo.
            correo_libre = correo if correo and not User.objects.filter(email__iexact=correo).exclude(
                pk=getattr(cuenta, "pk", None)).exists() else None
            if cuenta is None:
                cuenta = User.objects.create_user(
                    phone=telefono or None, email=correo_libre, role=User.Role.PATIENT,
                    tenant=paciente.tenant,
                    full_name=f"{paciente.first_name} {paciente.last_name}".strip(),
                )
            else:
                cuenta.tenant = paciente.tenant
                cuenta.is_active = True
                campos = ["tenant", "is_active"]
                if correo_libre and cuenta.email != correo_libre:
                    cuenta.email = correo_libre
                    campos.append("email")
                if por_correo and telefono and cuenta.phone != telefono and not User.objects.filter(
                        phone=telefono).exclude(pk=cuenta.pk).exists():
                    cuenta.phone = telefono
                    campos.append("phone")
                cuenta.save(update_fields=campos)
            paciente.user = cuenta
            paciente.save(update_fields=["user"])

        _auditar(request, paciente, "grant_app_access", telefono=telefono or "",
                 correo=correo if por_correo else "")
        return Response({**_estado(paciente), "bienvenida": _dar_la_bienvenida(paciente, cuenta, correo,
                                                                              telefono, por_correo)})

    def delete(self, request, pk):
        paciente = self._paciente(request, pk)
        cuenta = paciente.user
        if cuenta is not None:
            with transaction.atomic():
                paciente.user = None
                paciente.save(update_fields=["user"])
                cuenta.is_active = False
                cuenta.save(update_fields=["is_active"])
                _cerrar_sesiones(cuenta)
            _auditar(request, paciente, "revoke_app_access", telefono=cuenta.phone)
        return Response(_estado(paciente))


def _dar_la_bienvenida(paciente, cuenta, correo, telefono, por_correo):
    """
    El correo «Ya puedes usar la app», si la ficha tiene correo. Devuelve
    «enviada», «sin_correo» o «fallo»; un fallo no deshace la activación:
    la recepción puede explicárselo en persona.
    """
    from apps.accounts.correos_paciente import enviar_bienvenida

    if not correo:
        return "sin_correo"
    try:
        enviar_bienvenida(cuenta, correo, CORREO if por_correo else "whatsapp",
                          correo if por_correo else (telefono or paciente.phone))
    except Exception:
        logging.getLogger(__name__).exception(
            "No se pudo enviar la bienvenida a la app", extra={"patient_id": str(paciente.id)})
        return "fallo"
    return "enviada"


def _cerrar_sesiones(cuenta):
    """Invalida los tokens de refresco que tuviera la cuenta."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    for token in OutstandingToken.objects.filter(user=cuenta, expires_at__gt=timezone.now()):
        BlacklistedToken.objects.get_or_create(token=token)
