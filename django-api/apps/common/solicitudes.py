"""
Solicitudes de alta desde la página pública (clinube.com).

    POST  /api/v1/publico/solicitudes/                   datos de la clínica
    GET   /api/v1/platform/solicitudes/                  lo que ve el Super Administrador
    PATCH /api/v1/platform/solicitudes/{id}/             {estado, nota, avisar}
    POST  /api/v1/platform/solicitudes/{id}/aprobar/     {clinica, modalidad}: crea la clínica
    POST  /api/v1/platform/solicitudes/{id}/reenviar/    otro enlace para elegir la contraseña

Desde la página nadie crea una clínica: deja una solicitud y la
plataforma decide. Al aprobarla se crea la clínica con su administrador
sin contraseña, y le llega un enlace de un solo uso para elegirla. Ese
enlace es también la prueba de que el correo es suyo.

Odontología se responde a la brevedad; medicina y psicología, en un
plazo de hasta 12 horas (SolicitudClinica.PLAZO_HORAS).
"""

import io
import logging
from html import escape

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.models import PlatformConfiguration, SolicitudClinica, Tenant
from apps.common.permissions import HasRole

logger = logging.getLogger(__name__)
SUPERADMIN = HasRole.for_roles("superadmin")


def _ip(request):
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (reenviada.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


def _ocupado(correo, clinica):
    """El motivo por el que no se puede crear, o None."""
    if User.objects.filter(email__iexact=correo).exists():
        return {"correo": "Ya hay una cuenta con ese correo. Entra a la app o usa otro correo."}
    if Tenant.objects.filter(name__iexact=clinica).exists():
        return {"clinica": "Ya hay una clínica con ese nombre. Añade la ciudad o el sector."}
    return None


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
        motivo = _ocupado(datos["correo"], datos["clinica"])
        if motivo:
            raise serializers.ValidationError(motivo)
        if SolicitudClinica.objects.filter(correo__iexact=datos["correo"],
                                           estado=SolicitudClinica.Estado.PENDIENTE).exists():
            raise serializers.ValidationError(
                {"correo": "Ya tenemos una solicitud con este correo y la estamos revisando. "
                           "Te escribiremos en cuanto esté lista."})
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
        plazo = SolicitudClinica.PLAZO_HORAS.get(datos["tipo"])
        if datos.pop("sitio_web", ""):
            # Robot: se le responde como a cualquiera y no se guarda nada.
            return Response({"estado": "pendiente", "plazo_horas": plazo}, status=201)

        solicitud = SolicitudClinica.objects.create(**datos, estado=SolicitudClinica.Estado.PENDIENTE,
                                                    ip=_ip(request))
        for envio in (_correo_recibida, _aviso_a_la_plataforma):
            try:
                envio(solicitud)
            except Exception:
                # La solicitud ya está guardada y se ve en Plataforma.
                logger.exception("No se pudo enviar un correo de la solicitud %s", solicitud.id)
        return Response({"id": str(solicitud.id), "estado": solicitud.estado, "plazo_horas": plazo}, status=201)


@transaction.atomic
def _crear_clinica(solicitud, clinica, modalidad):
    from apps.common.funcionalidades import normalizar
    from apps.configuration.models import ClinicBranding

    funcionalidades = normalizar(None)
    if solicitud.tipo != SolicitudClinica.Tipo.ODONTOLOGIA:
        # El HCU-033 es el formulario de odontología del MSP.
        funcionalidades["formulario_033"] = False
    tenant = Tenant.objects.create(name=clinica, ruc=solicitud.ruc, is_active=True,
                                   phone=solicitud.telefono, email=solicitud.correo,
                                   modalidad=modalidad, funcionalidades=funcionalidades)
    call_command("bootstrap", tenant_name=tenant.name, stdout=io.StringIO())
    # Sin contraseña: la elige con el enlace que le llega al correo.
    admin = User(tenant=tenant, email=solicitud.correo, full_name=solicitud.nombre, role=User.Role.ADMIN)
    admin.set_unusable_password()
    admin.save()
    if tenant.modalidad == "consultorio":
        # Quien trabaja solo administra y atiende con la misma cuenta.
        from apps.accounts import atencion
        atencion.cambiar(admin, True)
    branding, _ = ClinicBranding.objects.get_or_create(tenant=tenant)
    branding.display_name = branding.display_name or clinica
    branding.phone = branding.phone or solicitud.telefono
    branding.email = branding.email or solicitud.correo
    branding.address = branding.address or solicitud.ciudad
    branding.save()
    solicitud.estado = SolicitudClinica.Estado.CREADA
    solicitud.tenant = tenant
    solicitud.save(update_fields=["estado", "tenant", "updated_at"])
    return tenant, admin


# ── Plataforma ───────────────────────────────────────────────────────

class SolicitudPlataformaSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    modalidad_nombre = serializers.CharField(source="get_modalidad_display", read_only=True)
    plazo_horas = serializers.IntegerField(read_only=True)
    responder_antes = serializers.DateTimeField(read_only=True)
    admin_pendiente = serializers.SerializerMethodField()
    # Al descartar: mandar o no el correo a quien la pidió.
    avisar = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = SolicitudClinica
        fields = ["id", "created_at", "tipo", "tipo_nombre", "modalidad", "modalidad_nombre", "estado",
                  "estado_nombre", "clinica", "ruc", "ciudad", "nombre", "correo", "telefono", "mensaje", "nota",
                  "tenant", "plazo_horas", "responder_antes", "admin_pendiente", "avisar"]
        read_only_fields = [f for f in fields if f not in ("estado", "nota", "avisar")]

    def get_admin_pendiente(self, s):
        """Creada, pero su administrador todavía no eligió contraseña."""
        if s.estado != SolicitudClinica.Estado.CREADA or not s.tenant_id:
            return False
        pendientes = self.context.get("sin_entrar")
        if pendientes is None:
            pendientes = _sin_entrar([s])
        return (s.tenant_id, s.correo.lower()) in pendientes

    def validate_estado(self, valor):
        if valor not in (SolicitudClinica.Estado.PENDIENTE, SolicitudClinica.Estado.ATENDIDA,
                         SolicitudClinica.Estado.DESCARTADA):
            raise serializers.ValidationError("Solo se marca como pendiente, atendida o descartada.")
        if self.instance and self.instance.estado == SolicitudClinica.Estado.CREADA:
            raise serializers.ValidationError("Esta solicitud ya tiene su clínica creada.")
        return valor


def _sin_entrar(solicitudes):
    """(clínica, correo) de los administradores que aún no tienen contraseña."""
    tenants = {s.tenant_id for s in solicitudes if s.tenant_id}
    if not tenants:
        return set()
    return {(t, c.lower()) for t, c in User.objects.filter(
        tenant_id__in=tenants, role=User.Role.ADMIN, password__startswith="!").values_list("tenant_id", "email")}


class SolicitudesPlataformaView(generics.ListAPIView):
    permission_classes = [SUPERADMIN]
    serializer_class = SolicitudPlataformaSerializer
    pagination_class = None

    def get_queryset(self):
        return SolicitudClinica.objects.all()[:300]

    def list(self, request, *args, **kwargs):
        filas = list(self.get_queryset())
        datos = self.get_serializer(filas, many=True, context={**self.get_serializer_context(),
                                                               "sin_entrar": _sin_entrar(filas)}).data
        return Response(datos)


class SolicitudPlataformaView(generics.UpdateAPIView):
    permission_classes = [SUPERADMIN]
    serializer_class = SolicitudPlataformaSerializer
    queryset = SolicitudClinica.objects.all()
    http_method_names = ["patch"]

    def perform_update(self, serializer):
        from apps.common.platform_views import _audit_platform

        antes = serializer.instance.estado
        avisar = serializer.validated_data.pop("avisar", False)
        solicitud = serializer.save()
        if solicitud.estado == antes:
            return
        _audit_platform(self.request, f"request_{solicitud.estado}", "SolicitudClinica", solicitud.id,
                        {"clinica": solicitud.clinica})
        if avisar and solicitud.estado == SolicitudClinica.Estado.DESCARTADA:
            try:
                _correo_descartada(solicitud)
            except Exception:
                logger.exception("No se pudo avisar del descarte de la solicitud %s", solicitud.id)


class AprobarSolicitudView(APIView):
    """Crea la clínica de una solicitud y manda el enlace a su administrador."""

    permission_classes = [SUPERADMIN]

    def post(self, request, pk):
        from apps.common.platform_views import _audit_platform

        with transaction.atomic():
            solicitud = generics.get_object_or_404(SolicitudClinica.objects.select_for_update(), pk=pk)
            if solicitud.estado == SolicitudClinica.Estado.CREADA:
                return Response({"detail": "Esta solicitud ya tiene su clínica creada."}, status=409)
            if solicitud.estado != SolicitudClinica.Estado.PENDIENTE:
                return Response({"detail": "Solo se aprueba una solicitud pendiente. Vuelve a marcarla "
                                           "como pendiente si quieres aprobarla."}, status=400)
            clinica = str(request.data.get("clinica") or solicitud.clinica).strip()
            modalidad = request.data.get("modalidad") or solicitud.modalidad
            if len(clinica) < 3:
                return Response({"detail": "Escribe el nombre de la clínica."}, status=400)
            if modalidad not in dict(Tenant.MODALIDADES):
                return Response({"detail": "Elige consultorio o clínica con equipo."}, status=400)
            motivo = _ocupado(solicitud.correo, clinica)
            if motivo:
                return Response({"detail": next(iter(motivo.values()))}, status=400)
            tenant, admin = _crear_clinica(solicitud, clinica, modalidad)
            _audit_platform(request, "approve_clinic_request", "Tenant", tenant.id,
                            {"name": tenant.name, "solicitud": str(solicitud.id), "admin": admin.email})

        correo = _mandar_enlace(request, solicitud, admin)
        datos = SolicitudPlataformaSerializer(solicitud).data
        return Response({**datos, "correo_enviado": correo}, status=201)


class ReenviarEnlaceView(APIView):
    """Otro enlace para el administrador que aún no eligió su contraseña."""

    permission_classes = [SUPERADMIN]

    def post(self, request, pk):
        solicitud = generics.get_object_or_404(SolicitudClinica, pk=pk, estado=SolicitudClinica.Estado.CREADA)
        admin = User.objects.filter(tenant_id=solicitud.tenant_id, email__iexact=solicitud.correo,
                                    role=User.Role.ADMIN, is_active=True).first()
        if admin is None:
            return Response({"detail": "El administrador de esta clínica ya no existe."}, status=404)
        if admin.has_usable_password():
            return Response({"detail": "Ya eligió su contraseña y puede entrar."}, status=400)
        if not _mandar_enlace(request, solicitud, admin):
            return Response({"detail": "No se pudo enviar el correo. Revisa el correo saliente en Plataforma."},
                            status=503)
        return Response({"detail": f"Enviamos un enlace nuevo a {admin.email}."})


def _mandar_enlace(request, solicitud, admin):
    from apps.accounts.google import client_id
    from apps.accounts.views import INVITACION_HORAS, enlace_de_bienvenida

    try:
        _correo_aprobada(solicitud, enlace_de_bienvenida(request, admin), INVITACION_HORAS, bool(client_id()))
    except Exception:
        logger.exception("No se pudo enviar el enlace de la clínica %s", solicitud.tenant_id)
        return False
    return True


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


def _plazo(s):
    """Cuándo respondemos, dicho como se le diría a la persona."""
    return f"en un plazo de hasta {s.plazo_horas} horas" if s.plazo_horas else "a la brevedad"


def _correo_recibida(s):
    servicio = s.get_tipo_display().lower()
    _enviar(
        f"Recibimos tu solicitud para {s.clinica}",
        f"Hola, {s.nombre}:\n\nRecibimos tu solicitud para abrir {s.clinica} en {settings.MARCA} "
        f"({servicio}). La revisamos y te respondemos {_plazo(s)}.\n\n"
        "Si la aprobamos, te llegará a este correo un enlace para elegir tu contraseña y entrar. "
        "No tienes que hacer nada más por ahora.\n",
        _parrafo(f"Hola, {escape(s.nombre)}:")
        + '<h1 style="margin:0 0 16px;font-size:22px;">Recibimos tu solicitud</h1>'
        + _parrafo(f"Anotamos <strong>{escape(s.clinica)}</strong> para <strong>{escape(servicio)}</strong>. "
                   f"Revisamos cada solicitud antes de abrir la cuenta y te respondemos {_plazo(s)}.")
        + _parrafo("Si la aprobamos, te llegará a este correo un enlace para elegir tu contraseña y entrar. "
                   "No tienes que hacer nada más por ahora."),
        s.correo, "Recibes este correo porque enviaste una solicitud desde clinube.com.")


def _correo_aprobada(s, enlace, horas, con_google):
    from apps.accounts.correos_paciente import _boton

    google = ("\nTambién puedes entrar con tu cuenta de Google, con este mismo correo.\n" if con_google else "")
    _enviar(
        f"Aprobamos {s.clinica} en {settings.MARCA}",
        f"Hola, {s.nombre}:\n\nAprobamos tu solicitud: {s.clinica} ya tiene su cuenta.\n\n"
        f"Elige tu contraseña aquí: {enlace}\nEl enlace vale {horas} horas y se usa una sola vez.{google}\n"
        f"Entras con tu correo: {s.correo}\n\n"
        "Para empezar: completa en Configuración el logotipo, la dirección y el teléfono (salen en recetas y "
        "certificados), crea los usuarios de tu equipo y registra tus tratamientos con sus precios.\n",
        _parrafo(f"Hola, {escape(s.nombre)}:")
        + f'<h1 style="margin:0 0 16px;font-size:22px;">{escape(s.clinica)} ya tiene su cuenta</h1>'
        + _parrafo(f"Aprobamos tu solicitud. Entras con tu correo <strong>{escape(s.correo)}</strong>; "
                   "solo falta que elijas tu contraseña.")
        + _boton("Elegir mi contraseña", enlace, "#0E7490")
        + _parrafo(f'<br><span style="color:#5B6474;font-size:13.5px;">El enlace vale {horas} horas y se usa '
                   "una sola vez." + (" También puedes entrar con tu cuenta de Google, con este mismo correo."
                                      if con_google else "") + "</span>")
        + _parrafo("Para empezar: completa en <strong>Configuración</strong> el logotipo, la dirección y el "
                   "teléfono (salen en recetas y certificados), crea los usuarios de tu equipo y registra tus "
                   "tratamientos con sus precios."),
        s.correo, "Recibes este correo porque pediste abrir una cuenta en clinube.com.")


def _correo_descartada(s):
    _enviar(
        f"Tu solicitud para {s.clinica}",
        f"Hola, {s.nombre}:\n\nRevisamos tu solicitud para {s.clinica} y por ahora no podemos abrir la "
        "cuenta. Si crees que hay un error o quieres contarnos algo más, responde a este correo.\n",
        _parrafo(f"Hola, {escape(s.nombre)}:")
        + '<h1 style="margin:0 0 16px;font-size:22px;">Sobre tu solicitud</h1>'
        + _parrafo(f"Revisamos tu solicitud para <strong>{escape(s.clinica)}</strong> y por ahora no podemos "
                   "abrir la cuenta.")
        + _parrafo("Si crees que hay un error o quieres contarnos algo más, responde a este correo."),
        s.correo, "Recibes este correo porque enviaste una solicitud desde clinube.com.")


def _aviso_a_la_plataforma(s):
    from apps.accounts.correos_paciente import _boton

    filas = "".join(f"<tr><td style='padding:3px 12px 3px 0;color:#5B6474;'>{k}</td><td>{escape(v)}</td></tr>"
                    for k, v in (("Servicio", s.get_tipo_display()), ("Modalidad", s.get_modalidad_display()),
                                 ("Clínica", s.clinica), ("RUC", s.ruc), ("Ciudad", s.ciudad),
                                 ("Contacto", s.nombre), ("Correo", s.correo), ("Teléfono", s.telefono),
                                 ("Mensaje", s.mensaje)) if v)
    plazo = f"Prometimos responder {_plazo(s)}."
    enlace = f"{(settings.PANEL_URL or '').rstrip('/')}/panel/plataforma/?tab=solicitudes"
    _enviar(
        f"Nueva solicitud: {s.get_tipo_display()} — {s.clinica}",
        f"{s.get_tipo_display()} — {s.clinica}\n{s.nombre} · {s.correo} · {s.telefono}\n{s.mensaje}\n\n"
        f"{plazo}\nSe aprueba o se descarta en Plataforma → Solicitudes: {enlace}\n",
        '<h1 style="margin:0 0 16px;font-size:20px;">Nueva solicitud desde la página</h1>'
        + f'<table style="font-size:14px;margin-bottom:14px;">{filas}</table>'
        + _parrafo(f"{plazo} Nada se crea hasta que la apruebes.")
        + _boton("Revisar la solicitud", enlace, "#0E7490"),
        _destino_plataforma(), "Aviso automático de la página pública.")
