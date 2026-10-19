"""
Alta y solicitudes desde la página pública (clinube.com).

    POST /api/v1/publico/solicitudes/                 datos de la clínica
    POST /api/v1/publico/solicitudes/{id}/confirmar/  {codigo, password} (odontología)
    GET  /api/v1/platform/solicitudes/                lo que ve el Super Administrador
    PATCH /api/v1/platform/solicitudes/{id}/          {estado, nota}

Odontología se crea al momento, pero solo con el código que llega al
correo: sin él cualquiera podría abrir una clínica con la dirección de
otro. Medicina y psicología todavía no existen como producto: queda la
solicitud y se avisa a la plataforma.
"""

import hashlib
import hmac
import io
import logging
import secrets
from datetime import timedelta
from html import escape

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDjango
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.models import PlatformConfiguration, SolicitudClinica, Tenant
from apps.common.permissions import HasRole

logger = logging.getLogger(__name__)
MINUTOS = 30
INTENTOS = 5


def _resumen(codigo):
    return hmac.new(settings.SECRET_KEY.encode(), codigo.encode(), hashlib.sha256).hexdigest()


def _ip(request):
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (reenviada.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


class SolicitudSerializer(serializers.ModelSerializer):
    # Campo trampa: invisible para una persona, los robots lo rellenan.
    sitio_web = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = SolicitudClinica
        fields = ["tipo", "modalidad", "clinica", "ruc", "ciudad", "nombre", "correo", "telefono", "mensaje",
                  "sitio_web"]

    def validate_clinica(self, valor):
        valor = valor.strip()
        if len(valor) < 3:
            raise serializers.ValidationError("Escribe el nombre de la clínica o consulta.")
        return valor

    def validate_ruc(self, valor):
        valor = (valor or "").strip()
        if valor and (not valor.isdigit() or len(valor) != 13):
            raise serializers.ValidationError("El RUC tiene 13 dígitos.")
        return valor

    def validate_correo(self, valor):
        return valor.strip().lower()

    def validate(self, datos):
        if datos.get("tipo") == SolicitudClinica.Tipo.ODONTOLOGIA:
            if User.objects.filter(email__iexact=datos["correo"]).exists():
                raise serializers.ValidationError(
                    {"correo": "Ya hay una cuenta con ese correo. Entra a la app o usa otro correo."})
            if Tenant.objects.filter(name__iexact=datos["clinica"]).exists():
                raise serializers.ValidationError(
                    {"clinica": "Ya hay una clínica con ese nombre. Añade la ciudad o el sector."})
        return datos


class SolicitudPublicaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "solicitudes"

    def post(self, request):
        s = SolicitudSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = dict(s.validated_data)
        if datos.pop("sitio_web", ""):
            # Robot: se le responde como a cualquiera y no se guarda nada.
            return Response({"estado": "pendiente"}, status=201)

        if datos["tipo"] == SolicitudClinica.Tipo.ODONTOLOGIA:
            codigo = f"{secrets.randbelow(10**6):06d}"
            solicitud = SolicitudClinica.objects.create(
                **datos, estado=SolicitudClinica.Estado.VERIFICANDO, ip=_ip(request),
                codigo_hash=_resumen(codigo), codigo_vence=timezone.now() + timedelta(minutes=MINUTOS))
            try:
                _correo_codigo(solicitud, codigo)
            except Exception:
                logger.exception("No se pudo enviar el código del alta de clínica")
                solicitud.delete()
                return Response({"detail": "No pudimos enviar el correo. Revisa la dirección e inténtalo de nuevo."},
                                status=503)
            return Response({"id": str(solicitud.id), "estado": solicitud.estado, "minutos": MINUTOS}, status=201)

        solicitud = SolicitudClinica.objects.create(**datos, estado=SolicitudClinica.Estado.PENDIENTE,
                                                    ip=_ip(request))
        for envio in (_correo_recibida, _aviso_a_la_plataforma):
            try:
                envio(solicitud)
            except Exception:
                # La solicitud ya está guardada y se ve en Plataforma.
                logger.exception("No se pudo enviar un correo de la solicitud %s", solicitud.id)
        return Response({"id": str(solicitud.id), "estado": solicitud.estado}, status=201)


class ConfirmarSolicitudView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, pk):
        solicitud = SolicitudClinica.objects.filter(
            pk=pk, estado=SolicitudClinica.Estado.VERIFICANDO).first()
        if solicitud is None or solicitud.codigo_vence < timezone.now() or solicitud.intentos >= INTENTOS:
            return Response({"detail": "El código caducó. Vuelve a llenar el formulario para recibir otro."},
                            status=400)
        codigo = str(request.data.get("codigo") or "").strip()
        if not hmac.compare_digest(_resumen(codigo), solicitud.codigo_hash):
            solicitud.intentos += 1
            solicitud.save(update_fields=["intentos", "updated_at"])
            return Response({"detail": "Ese código no es el que enviamos."}, status=400)
        password = str(request.data.get("password") or "")
        provisional = User(email=solicitud.correo, full_name=solicitud.nombre)
        try:
            validate_password(password, user=provisional)
        except ErrorDjango as e:
            return Response({"detail": " ".join(e.messages)}, status=400)
        if User.objects.filter(email__iexact=solicitud.correo).exists() or \
                Tenant.objects.filter(name__iexact=solicitud.clinica).exists():
            return Response({"detail": "Ese correo o ese nombre de clínica se registraron hace un momento."},
                            status=400)

        tenant = _crear_clinica(solicitud, password)
        try:
            _correo_bienvenida(solicitud)
        except Exception:
            logger.exception("No se pudo enviar la bienvenida a la clínica %s", tenant.id)
        return Response({"estado": "creada", "clinica": tenant.name, "correo": solicitud.correo}, status=201)


@transaction.atomic
def _crear_clinica(solicitud, password):
    from apps.accounts.models import AuditLog
    from apps.common.funcionalidades import normalizar
    from apps.configuration.models import ClinicBranding

    tenant = Tenant.objects.create(name=solicitud.clinica, ruc=solicitud.ruc, is_active=True,
                                   phone=solicitud.telefono, email=solicitud.correo,
                                   modalidad=solicitud.modalidad, funcionalidades=normalizar(None))
    call_command("bootstrap", tenant_name=tenant.name, stdout=io.StringIO())
    admin = User(tenant=tenant, email=solicitud.correo, full_name=solicitud.nombre, role=User.Role.ADMIN)
    admin.set_password(password)
    admin.save()
    if tenant.modalidad == "consultorio":
        # Quien trabaja solo administra y atiende con la misma cuenta.
        from apps.accounts import atencion
        atencion.cambiar(admin, True)
    branding, _ = ClinicBranding.objects.get_or_create(tenant=tenant)
    branding.display_name = branding.display_name or solicitud.clinica
    branding.phone = branding.phone or solicitud.telefono
    branding.email = branding.email or solicitud.correo
    branding.address = branding.address or solicitud.ciudad
    branding.save()
    solicitud.estado = SolicitudClinica.Estado.CREADA
    solicitud.tenant = tenant
    solicitud.codigo_hash = ""
    solicitud.save(update_fields=["estado", "tenant", "codigo_hash", "updated_at"])
    AuditLog.objects.create(tenant=tenant, user=admin, action="self_signup_clinic", entity_type="Tenant",
                            entity_id=str(tenant.id), metadata={"solicitud": str(solicitud.id)})
    return tenant


# ── Plataforma ───────────────────────────────────────────────────────

class SolicitudPlataformaSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = SolicitudClinica
        fields = ["id", "created_at", "tipo", "tipo_nombre", "modalidad", "estado", "estado_nombre", "clinica", "ruc",
                  "ciudad", "nombre", "correo", "telefono", "mensaje", "nota", "tenant"]
        read_only_fields = [f for f in fields if f not in ("estado", "nota")]

    def validate_estado(self, valor):
        if valor not in (SolicitudClinica.Estado.PENDIENTE, SolicitudClinica.Estado.ATENDIDA,
                         SolicitudClinica.Estado.DESCARTADA):
            raise serializers.ValidationError("Solo se marca como pendiente, atendida o descartada.")
        return valor


class SolicitudesPlataformaView(generics.ListAPIView):
    permission_classes = [HasRole.for_roles("superadmin")]
    serializer_class = SolicitudPlataformaSerializer
    pagination_class = None

    def get_queryset(self):
        # Las que esperan el código no son de nadie todavía: no se enseñan.
        return SolicitudClinica.objects.exclude(estado=SolicitudClinica.Estado.VERIFICANDO)[:300]


class SolicitudPlataformaView(generics.UpdateAPIView):
    permission_classes = [HasRole.for_roles("superadmin")]
    serializer_class = SolicitudPlataformaSerializer
    queryset = SolicitudClinica.objects.all()
    http_method_names = ["patch"]


# ── Correos ──────────────────────────────────────────────────────────

def _marca():
    from apps.accounts.correos_paciente import marca_de

    m = marca_de(None)
    config = PlatformConfiguration.objects.first()
    m["correo"] = (getattr(config, "titular_correo", "") or "")
    return m


def _destino_plataforma():
    config = PlatformConfiguration.objects.first()
    return (getattr(config, "titular_correo", "") or getattr(config, "smtp_user", "")
            or settings.DEFAULT_FROM_EMAIL)


def _parrafo(texto):
    return f'<p style="margin:0 0 14px;font-size:15px;line-height:1.55;">{texto}</p>'


def _enviar(asunto, texto, cuerpo_html, destino, motivo):
    from apps.accounts.correos_paciente import _documento
    from apps.accounts.correos_paciente import _enviar as enviar

    marca = _marca()
    html = _documento(marca, asunto, '<tr><td style="padding:30px 28px 8px;">' + cuerpo_html + "</td></tr>",
                      motivo)
    enviar(asunto, texto, html, destino, marca)


def _correo_codigo(s, codigo):
    _enviar(
        f"{codigo} es tu código para crear {s.clinica} en {settings.MARCA}",
        f"Hola, {s.nombre}:\n\nTu código para crear {s.clinica} en {settings.MARCA} es {codigo}.\n"
        f"Vale {MINUTOS} minutos. Si no lo pediste, ignora este correo: sin el código no se crea nada.\n",
        _parrafo(f"Hola, {escape(s.nombre)}:")
        + '<h1 style="margin:0 0 16px;font-size:22px;">Tu código para crear tu clínica</h1>'
        + f'<div style="font-size:34px;font-weight:700;letter-spacing:8px;margin:0 0 18px;'
          f"font-family:'SF Mono',Menlo,Consolas,monospace;\">{codigo}</div>"
        + _parrafo(f"Escríbelo en la página para terminar de crear <strong>{escape(s.clinica)}</strong>. "
                   f"Vale durante {MINUTOS} minutos."),
        s.correo, "Recibes este correo porque alguien quiso crear una clínica con tu dirección. "
                  "Si no fuiste tú, ignóralo: sin el código no se crea nada.")


def _correo_bienvenida(s):
    from apps.accounts.correos_paciente import _boton

    enlace = f"{(settings.PANEL_URL or '').rstrip('/')}/login/"
    _enviar(
        f"{s.clinica} ya está en {settings.MARCA}",
        f"Hola, {s.nombre}:\n\n{s.clinica} ya está creada. Entra con {s.correo} en {enlace}\n\n"
        "Lo primero: completa los datos de la clínica en Configuración (logotipo, dirección y teléfono), "
        "crea los usuarios de tu equipo y registra los tratamientos con sus precios.\n",
        _parrafo(f"Hola, {escape(s.nombre)}:")
        + f'<h1 style="margin:0 0 16px;font-size:22px;">{escape(s.clinica)} ya está lista</h1>'
        + _parrafo(f"Entra con <strong>{escape(s.correo)}</strong> y la contraseña que elegiste.")
        + _boton("Entrar a Clinube", enlace, "#0E7490")
        + _parrafo("<br>Para empezar: completa en <strong>Configuración</strong> el logotipo, la dirección y "
                   "el teléfono (salen en recetas y certificados), crea los usuarios de tu equipo y registra "
                   "tus tratamientos con sus precios."),
        s.correo, "Recibes este correo porque acabas de crear tu clínica.")


def _correo_recibida(s):
    _enviar(
        f"Recibimos tu solicitud para {s.get_tipo_display().lower()}",
        f"Hola, {s.nombre}:\n\nRecibimos tu solicitud para {s.clinica} ({s.get_tipo_display()}). "
        "Te escribiremos a este correo en cuanto esté disponible.\n",
        _parrafo(f"Hola, {escape(s.nombre)}:")
        + '<h1 style="margin:0 0 16px;font-size:22px;">Recibimos tu solicitud</h1>'
        + _parrafo(f"Anotamos <strong>{escape(s.clinica)}</strong> para <strong>"
                   f"{escape(s.get_tipo_display().lower())}</strong>. Por ahora Clinube está disponible para "
                   "odontología; te escribiremos a este correo en cuanto podamos abrir tu consulta."),
        s.correo, "Recibes este correo porque enviaste una solicitud desde clinube.com.")


def _aviso_a_la_plataforma(s):
    filas = "".join(f"<tr><td style='padding:3px 12px 3px 0;color:#5B6474;'>{k}</td><td>{escape(v)}</td></tr>"
                    for k, v in (("Servicio", s.get_tipo_display()), ("Clínica", s.clinica), ("RUC", s.ruc),
                                 ("Ciudad", s.ciudad), ("Contacto", s.nombre), ("Correo", s.correo),
                                 ("Teléfono", s.telefono), ("Mensaje", s.mensaje)) if v)
    _enviar(
        f"Nueva solicitud: {s.get_tipo_display()} — {s.clinica}",
        f"{s.get_tipo_display()} — {s.clinica}\n{s.nombre} · {s.correo} · {s.telefono}\n{s.mensaje}\n",
        '<h1 style="margin:0 0 16px;font-size:20px;">Nueva solicitud desde la página</h1>'
        + f'<table style="font-size:14px;margin-bottom:14px;">{filas}</table>'
        + _parrafo("La ves también en Plataforma → Solicitudes."),
        _destino_plataforma(), "Aviso automático de la página pública.")
