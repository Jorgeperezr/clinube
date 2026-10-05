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

Requiere la función «App del paciente» activa en la clínica.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, User
from apps.common.funcionalidades import activa
from apps.common.permisos_funcionalidad import RequiereFuncionalidad
from apps.common.permissions import HasRole
from apps.common.telefonos import normalizar_telefono
from apps.patients.models import Patient


def _estado(paciente):
    cuenta = paciente.user if paciente.user_id and paciente.user.is_active else None
    telefono = normalizar_telefono(paciente.phone)
    return {
        "activo": cuenta is not None,
        "telefono": cuenta.phone if cuenta else telefono,
        # El de la ficha, normalizado: si no coincide con el de la cuenta,
        # el paciente cambió de número y hay que volver a activar.
        "telefono_ficha": telefono,
        "telefono_valido": bool(telefono),
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
        if not telefono:
            return Response(
                {"detail": "La ficha no tiene un teléfono móvil válido. Corrígelo en los "
                           "datos del paciente: es el número con el que entrará a la app."},
                status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            cuenta = User.objects.select_for_update().filter(phone=telefono).first()
            if cuenta is not None and cuenta.role != User.Role.PATIENT:
                return Response(
                    {"detail": "Ese teléfono es el de una persona del equipo. Cada número "
                               "entra a una sola cuenta: usa otro para el paciente."},
                    status=status.HTTP_409_CONFLICT)
            otra = (Patient.objects.filter(user=cuenta).exclude(pk=paciente.pk).first()
                    if cuenta is not None else None)
            if otra is not None and otra.is_active:
                return Response(
                    {"detail": "Ese teléfono ya da acceso a la app a otra ficha (de otro "
                               "paciente o de otra clínica). Cada número entra a una sola "
                               "ficha: revisa el teléfono de las dos."},
                    status=status.HTTP_409_CONFLICT)
            if otra is not None:
                # La otra ficha está borrada: el número queda libre.
                otra.user = None
                otra.save(update_fields=["user"])

            # Si la ficha ya tenía una cuenta con otro número (cambió de
            # teléfono), esa se desactiva: el acceso va con el número nuevo.
            anterior = paciente.user if paciente.user_id and paciente.user_id != getattr(cuenta, "id", None) else None
            if anterior is not None:
                anterior.is_active = False
                anterior.save(update_fields=["is_active"])

            if cuenta is None:
                cuenta = User.objects.create_user(
                    phone=telefono, role=User.Role.PATIENT, tenant=paciente.tenant,
                    full_name=f"{paciente.first_name} {paciente.last_name}".strip(),
                )
            else:
                cuenta.tenant = paciente.tenant
                cuenta.is_active = True
                cuenta.save(update_fields=["tenant", "is_active"])
            paciente.user = cuenta
            paciente.save(update_fields=["user"])

        _auditar(request, paciente, "grant_app_access", telefono=telefono)
        return Response(_estado(paciente))

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


def _cerrar_sesiones(cuenta):
    """Invalida los tokens de refresco que tuviera la cuenta."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    for token in OutstandingToken.objects.filter(user=cuenta, expires_at__gt=timezone.now()):
        BlacklistedToken.objects.get_or_create(token=token)
