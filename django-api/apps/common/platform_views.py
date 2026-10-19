"""
Panel de plataforma (SaaS) — Sprint 21, según especificación:

    Super Administrador (plataforma) — SOLO administra la plataforma:
    1. Dashboard: clínicas totales / activas / suspendidas, admins de clínica.
    2. Gestión de Clínicas: registrar, editar datos generales, activar/
       suspender, credenciales del administrador.
    3. Administradores de Clínicas: solo el admin principal de cada una
       (restablecer contraseña, activar/desactivar, actualizar correo).
    4. Auditoría: solo las acciones del propio Super Administrador.
    5. Configuración General de la plataforma.

PRINCIPIO DE AISLAMIENTO: el Super Administrador NO accede a información
operativa de las clínicas (pacientes, historias, citas, pagos). Ningún
endpoint de este módulo expone esos datos, y los endpoints operativos lo
rechazan por rol (verificado por tests).
"""

import secrets

from django.core.management import call_command
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import atencion
from apps.accounts.models import AuditLog, User
from apps.common.models import PlatformConfiguration, Tenant
from apps.common.permissions import HasRole

IS_SUPERADMIN = HasRole.for_roles("superadmin")

# Acciones de plataforma que aparecen en el módulo de Auditoría
PLATFORM_ACTIONS = [
    "create_clinic", "update_clinic", "activate_clinic", "deactivate_clinic",
    "create_clinic_admin", "update_clinic_admin", "reset_clinic_admin_password",
    "update_platform_config", "update_clinic_identity",
    "publish_feature", "unpublish_feature", "test_email",
]


def _audit_platform(request, action, entity_type, entity_id, metadata=None):
    AuditLog.objects.create(
        tenant=None,  # acciones de plataforma: no pertenecen a una clínica
        user=request.user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
    )


def _principal_admin(tenant):
    """El administrador principal: el admin más antiguo de la clínica."""
    return (
        User.objects.filter(tenant=tenant, role=User.Role.ADMIN)
        .order_by("created_at")
        .first()
    )


# ─────────────────────────── Clínicas ───────────────────────────

class ClinicSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()
    condiciones = serializers.SerializerMethodField()
    funcionalidades = serializers.JSONField(required=False)

    class Meta:
        model = Tenant
        fields = ["id", "name", "ruc", "address", "phone", "email",
                  "is_active", "es_prueba", "modalidad", "admin", "condiciones", "funcionalidades",
                  "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_admin(self, obj):
        admin = _principal_admin(obj)
        if not admin:
            return None
        return {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
            # Se expone para que el panel distinga «le entregué las
            # credenciales» de «la clínica ya tomó posesión de su cuenta».
            # Sin esto, una clínica que nunca entró se ve igual que una que
            # lleva meses trabajando.
            "must_change_password": admin.must_change_password,
        }

    def get_condiciones(self, obj):
        """La aceptación de la versión vigente de las condiciones, o None."""
        from apps.common.legal import CONDICIONES_VERSION
        from apps.common.models import AceptacionCondiciones

        a = AceptacionCondiciones.objects.filter(tenant=obj, version=CONDICIONES_VERSION).first()
        if not a:
            return None
        return {"version": a.version, "fecha": a.created_at, "por": a.correo}

    def validate_funcionalidades(self, value):
        """
        Se normaliza SIEMPRE: lo que llegue se recorta al catálogo y lo
        que falte se rellena. Guardar tal cual lo que mande el panel
        dejaría claves inventadas en la base y, peor, clínicas sin
        alguna clave el día que se añada una funcionalidad nueva.
        """
        from apps.common.funcionalidades import normalizar
        return normalizar(value)

    def to_representation(self, instance):
        from apps.common.funcionalidades import normalizar
        datos = super().to_representation(instance)
        # Igual al leer: una clínica creada antes de que existiera una
        # funcionalidad la recibe con su valor por defecto en vez de un
        # hueco que el panel pintaría como «apagada».
        datos["funcionalidades"] = normalizar(instance.funcionalidades)
        return datos

    def validate_name(self, value):
        qs = Tenant.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una clínica con ese nombre.")
        return value.strip()


def _credencial_temporal(usuario):
    """
    Genera la contraseña, la deja puesta y la devuelve UNA vez.

    Nadie la inventa y nadie la guarda en claro. Y se marca la cuenta
    como pendiente de cambio: mientras no elija la suya, lo único que
    puede hacer es elegirla. Sin esa marca, la contraseña que entrega el
    dueño de la plataforma sigue siendo válida para siempre y él la
    conoce, con lo que «entregar las credenciales» no entrega nada.
    """
    temporal = secrets.token_urlsafe(12)
    usuario.set_password(temporal)
    usuario.must_change_password = True
    usuario.save()
    return temporal


class ClinicListCreateView(generics.ListCreateAPIView):
    serializer_class = ClinicSerializer
    permission_classes = [IS_SUPERADMIN]
    pagination_class = None

    def get_queryset(self):
        return Tenant.objects.order_by("name")

    def perform_create(self, serializer):
        # Una clínica nueva SIEMPRE nace activa; suspenderla es una acción
        # explícita posterior (PATCH). Esto también neutraliza la semántica
        # de checkbox de los formularios (boolean ausente = False).
        from apps.common.funcionalidades import normalizar
        tenant = serializer.save(
            is_active=True,
            funcionalidades=normalizar(serializer.validated_data.get("funcionalidades")),
        )
        # Siembra del catálogo base de la clínica nueva (Sprint 1)
        call_command("bootstrap", tenant_name=tenant.name)
        _audit_platform(self.request, "create_clinic", "Tenant", tenant.id,
                        {"name": tenant.name})
        self._alta_del_administrador(tenant)

    def _alta_del_administrador(self, tenant):
        """
        Si el alta trae los datos del administrador, se crea aquí mismo.

        Dar de alta una clínica eran TRES actos en dos pestañas: crear la
        clínica, ir a «Administradores» a crear su admin inventándole una
        contraseña, y restablecerla para obtener una generada. Son tres
        pasos para un solo acto, y el del medio pedía a una persona que se
        inventara un secreto, que es como se acaban poniendo contraseñas
        como «clinica2026».

        Sigue siendo opcional: quien prefiera crear la clínica ahora y su
        administrador más tarde puede hacerlo como siempre.
        """
        email = str(self.request.data.get("admin_email", "")).strip()
        full_name = str(self.request.data.get("admin_full_name", "")).strip()
        if not email:
            return
        if User.objects.filter(email__iexact=email).exists():
            # La clínica ya está creada: no se deshace, se avisa. Cancelar
            # el alta entera por un correo repetido sería peor.
            self._credenciales = {"error": "Ya existe un usuario con ese correo."}
            return
        admin = User(tenant=tenant, email=email,
                     full_name=full_name or email, role=User.Role.ADMIN)
        temporal = _credencial_temporal(admin)
        if tenant.modalidad == "consultorio":
            # El profesional que trabaja solo administra y atiende con la
            # misma cuenta: nace con su ficha de doctor.
            atencion.cambiar(admin, True)
        _audit_platform(self.request, "create_clinic_admin", "User", admin.id,
                        {"email": admin.email, "clinic": tenant.name})
        self._credenciales = {
            "email": admin.email,
            "temporary_password": temporal,
            "note": ("Entregar por un canal seguro. No se puede volver a "
                     "consultar: al ingresar, la clínica deberá elegir su "
                     "propia contraseña."),
        }

    def create(self, request, *args, **kwargs):
        self._credenciales = None
        respuesta = super().create(request, *args, **kwargs)
        if self._credenciales:
            respuesta.data["admin"] = self._credenciales
        return respuesta


class ClinicDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ClinicSerializer
    permission_classes = [IS_SUPERADMIN]
    queryset = Tenant.objects.all()

    def perform_update(self, serializer):
        previous_active = serializer.instance.is_active
        previous_prueba = serializer.instance.es_prueba
        previous_modalidad = serializer.instance.modalidad
        tenant = serializer.save()
        if previous_modalidad != tenant.modalidad and tenant.modalidad == "consultorio":
            # Pasar a consultorio deja atendiendo a su administrador; al
            # revés no se le quita nada: puede seguir atendiendo en una
            # clínica con equipo.
            admin = _principal_admin(tenant)
            if admin:
                atencion.cambiar(admin, True)
        if previous_active != tenant.is_active:
            action = "activate_clinic" if tenant.is_active else "deactivate_clinic"
        else:
            action = "update_clinic"
        metadata = {"name": tenant.name}
        if previous_prueba != tenant.es_prueba:
            # Que conste quién convirtió una clínica en «de pruebas»: desde
            # ese momento ve funciones que las demás todavía no tienen.
            metadata["es_prueba"] = tenant.es_prueba
        if previous_modalidad != tenant.modalidad:
            metadata["modalidad"] = tenant.modalidad
        _audit_platform(self.request, action, "Tenant", tenant.id, metadata)


# ─────────────────────── Identidad visual ───────────────────────

class ClinicIdentidadView(APIView):
    """
    GET/PATCH /api/v1/platform/clinics/{pk}/identidad/ — logotipos, paleta
    y temas de una clínica: se dan al crearla y se pueden cambiar después.

    Es su imagen, no sus datos: no rompe el aislamiento de la plataforma
    (no se ve ningún paciente, cita ni pago). Acepta lo mismo que
    Configuración → Identidad visual, por el mismo camino
    (apps/configuration/identidad.py): `logo`, `logo_oscuro`, `icono`,
    `<campo>_clear`, `paleta` y `theme`. Con la paleta se generan los
    temas de la clínica y, si aún tenía el de fábrica, se le pone el
    principal.
    """

    permission_classes = [IS_SUPERADMIN]

    def _branding(self, pk):
        from apps.configuration.models import ClinicBranding

        tenant = Tenant.objects.filter(pk=pk).first()
        if tenant is None:
            return None
        branding, _ = ClinicBranding.objects.get_or_create(tenant=tenant)
        return branding

    def _respuesta(self, branding):
        from apps.configuration.serializers import ClinicBrandingSerializer

        datos = ClinicBrandingSerializer(branding).data
        return Response({clave: datos[clave] for clave in (
            "logo_url", "logo_oscuro_url", "icono_url", "theme", "paleta", "temas", "updated_at")})

    def get(self, request, pk):
        branding = self._branding(pk)
        if branding is None:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        return self._respuesta(branding)

    def patch(self, request, pk):
        from apps.configuration import identidad

        branding = self._branding(pk)
        if branding is None:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        try:
            identidad.actualizar(branding, request.data, request.FILES)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        branding.save()
        cambios = sorted(set(request.FILES) | {
            clave for clave in request.data
            if clave in ("paleta", "theme") or clave.endswith("_clear")})
        _audit_platform(request, "update_clinic_identity", "Tenant", branding.tenant_id,
                        {"name": branding.tenant.name, "cambios": cambios})
        return self._respuesta(branding)


# ──────────────── Administradores de clínica ────────────────

class ClinicAdminView(APIView):
    """
    GET   → datos del administrador principal de la clínica.
    POST  → crear el administrador (si la clínica no tiene).
    PATCH → actualizar correo / activar-desactivar la cuenta.
    """

    permission_classes = [IS_SUPERADMIN]

    def _tenant(self, pk):
        try:
            return Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            return None

    def get(self, request, pk):
        tenant = self._tenant(pk)
        if not tenant:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        admin = _principal_admin(tenant)
        if not admin:
            return Response({"admin": None})
        return Response({"admin": {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
        }})

    def post(self, request, pk):
        tenant = self._tenant(pk)
        if not tenant:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        if _principal_admin(tenant):
            return Response(
                {"detail": "La clínica ya tiene administrador. Usa restablecer contraseña o actualizar correo."},
                status=400,
            )
        email = str(request.data.get("email", "")).strip()
        full_name = str(request.data.get("full_name", "")).strip()
        if not email or not full_name:
            return Response(
                {"detail": "email y full_name son obligatorios."}, status=400,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "Ya existe un usuario con ese correo."}, status=400)
        user = User(tenant=tenant, email=email, full_name=full_name, role=User.Role.ADMIN)
        # La contraseña la genera el sistema y se muestra una vez. Antes se
        # exigía que el Super Administrador escribiera una de 10+
        # caracteres: pedirle a una persona que invente un secreto para
        # otra es como se acaban poniendo contraseñas como «clinica2026»,
        # y además se la queda quien la inventó.
        temporal = _credencial_temporal(user)
        _audit_platform(request, "create_clinic_admin", "User", user.id,
                        {"email": user.email, "clinic": tenant.name})
        return Response({
            "id": str(user.id),
            "email": user.email,
            "temporary_password": temporal,
            "note": ("Entregar por un canal seguro. No se puede volver a "
                     "consultar: al ingresar, deberá elegir su propia "
                     "contraseña."),
        }, status=201)

    def patch(self, request, pk):
        tenant = self._tenant(pk)
        if not tenant:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        admin = _principal_admin(tenant)
        if not admin:
            return Response({"detail": "La clínica no tiene administrador."}, status=404)

        changes = {}
        if "email" in request.data:
            new_email = str(request.data["email"]).strip()
            if User.objects.filter(email__iexact=new_email).exclude(id=admin.id).exists():
                return Response({"detail": "Ese correo ya está en uso."}, status=400)
            changes["previous_email"] = admin.email
            admin.email = new_email
        if "is_active" in request.data:
            raw = request.data["is_active"]
            admin.is_active = raw in (True, 1, "1", "true", "True", "TRUE")
            changes["is_active"] = admin.is_active
        admin.save()
        _audit_platform(request, "update_clinic_admin", "User", admin.id,
                        {"clinic": tenant.name, **changes})
        return Response({"admin": {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
        }})


class ClinicAdminResetPasswordView(APIView):
    """
    POST /platform/clinics/{pk}/admin/reset-password/ — genera una
    contraseña temporal segura y la devuelve UNA sola vez (no se guarda
    en claro en ningún lado). El Super Administrador se la entrega al
    admin de la clínica por un canal seguro.
    """

    permission_classes = [IS_SUPERADMIN]

    def post(self, request, pk):
        try:
            tenant = Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        admin = _principal_admin(tenant)
        if not admin:
            return Response({"detail": "La clínica no tiene administrador."}, status=404)

        temp_password = _credencial_temporal(admin)
        _audit_platform(request, "reset_clinic_admin_password", "User", admin.id,
                        {"clinic": tenant.name, "email": admin.email})
        return Response({
            "email": admin.email,
            "temporary_password": temp_password,
            "note": ("Entregar por un canal seguro. No se puede volver a "
                     "consultar: al ingresar, deberá elegir su propia "
                     "contraseña."),
        })


# ─────────────────────────── Dashboard ───────────────────────────

class PlatformOverviewView(APIView):
    """Dashboard del Super Administrador — SOLO datos de plataforma."""

    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        clinics = Tenant.objects.all()
        return Response({
            "clinics_total": clinics.count(),
            "clinics_active": clinics.filter(is_active=True).count(),
            "clinics_suspended": clinics.filter(is_active=False).count(),
            "clinic_admins_total": User.objects.filter(role=User.Role.ADMIN).count(),
        })


# ─────────────────────────── Auditoría ───────────────────────────

class PlatformAuditView(APIView):
    """Solo las acciones realizadas por el Super Administrador."""

    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        logs = (
            AuditLog.objects.filter(
                user__role=User.Role.SUPERADMIN,
                action__in=PLATFORM_ACTIONS,
            )
            .select_related("user")
            .order_by("-created_at")[:200]
        )
        return Response({"results": [{
            "id": str(log.id),
            "user": log.user.email if log.user else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "metadata": log.metadata,
            "created_at": log.created_at.isoformat(),
        } for log in logs]})


# ──────────────────── Configuración general ────────────────────

class PlatformConfigSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    smtp_password_set = serializers.SerializerMethodField()
    # Por dónde sale hoy el correo: «plataforma» (lo de este formulario),
    # «entorno» (EMAIL_HOST del .env) o vacío (no sale).
    correo_origen = serializers.SerializerMethodField()

    class Meta:
        model = PlatformConfiguration
        fields = ["platform_name", "logo_url", "smtp_host", "smtp_port", "smtp_user",
                  "smtp_password", "smtp_password_set", "correo_origen", "timezone", "currency",
                  "titular_nombre", "titular_ruc", "titular_correo", "proveedor_correo",
                  "canal_codigo_paciente", "google_client_id", "updated_at"]
        read_only_fields = ["updated_at"]

    def get_smtp_password_set(self, obj):
        return bool(obj.smtp_password)

    def get_correo_origen(self, obj):
        from apps.common.correo import datos_smtp

        datos = datos_smtp()
        return datos["origen"] if datos else ""

    def validate_smtp_password(self, valor):
        # Cifrada, como los tokens de WhatsApp: un volcado de la base no
        # debe entregar la contraseña del correo.
        from apps.common.secretos import cifrar

        return cifrar(valor)

    def validate_smtp_host(self, valor):
        return (valor or "").strip()

    def validate(self, datos):
        # Pasar a correo sin correo configurado dejaría a todos los
        # pacientes sin poder entrar: se dice antes de guardar.
        from apps.common.correo import datos_smtp

        if datos.get("canal_codigo_paciente") == PlatformConfiguration.CANAL_CORREO:
            host = datos.get("smtp_host", self.instance.smtp_host if self.instance else "")
            if not (host or "").strip() and datos_smtp() is None:
                raise serializers.ValidationError({"canal_codigo_paciente": (
                    "Para mandar el código por correo, primero configura el correo saliente "
                    "y comprueba con «Enviar correo de prueba» que llega.")})
        return datos


class FuncionalidadesView(APIView):
    """
    GET /api/v1/platform/funcionalidades/ — el catálogo de funciones, con
    su tipo (incluida o adicional), su fase (en prueba o estable), si
    viene encendida en una clínica nueva y de dónde salió. Plataforma lo
    pinta tal cual: una función nueva aparece sola al desplegarla.

    Trae también qué clínicas son de prueba, que son las únicas que ven
    lo que está en prueba.
    """

    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        from apps.common.funcionalidades import TIPOS, catalogo_publico

        return Response({
            "tipos": TIPOS,
            "funcionalidades": catalogo_publico(),
            "clinicas_de_prueba": [
                {"id": str(t.id), "name": t.name}
                for t in Tenant.objects.filter(es_prueba=True).order_by("name")
            ],
        })


class FuncionalidadPublicacionView(APIView):
    """
    PATCH /api/v1/platform/funcionalidades/{clave}/ con {"publicada": true}
    — da a todas las clínicas una función que estaba en prueba; con false
    la devuelve a prueba (vuelve a verse solo en las clínicas de prueba).
    Ni publicar ni retirar borra datos.
    """

    permission_classes = [IS_SUPERADMIN]

    def patch(self, request, clave):
        from apps.common.funcionalidades import CATALOGO, catalogo_publico, publicar

        if clave not in CATALOGO:
            return Response({"detail": "Esa función no existe."}, status=404)
        publicada = request.data.get("publicada")
        if not isinstance(publicada, bool):
            return Response({"detail": "Indica publicada: verdadero o falso."}, status=400)
        try:
            publicar(clave, publicada)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        _audit_platform(request, "publish_feature" if publicada else "unpublish_feature",
                        "Funcionalidad", clave, {"name": CATALOGO[clave]["nombre"]})
        return Response(next(f for f in catalogo_publico() if f["clave"] == clave))


class PlatformConfigView(APIView):
    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        return Response(PlatformConfigSerializer(PlatformConfiguration.get_solo()).data)

    def patch(self, request):
        config = PlatformConfiguration.get_solo()
        serializer = PlatformConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _audit_platform(request, "update_platform_config", "PlatformConfiguration",
                        config.id, {"fields": list(request.data.keys())})
        return Response(PlatformConfigSerializer(config).data)


class CorreoDePruebaView(APIView):
    """
    POST /api/v1/platform/config/correo-de-prueba/ {"destino": "…"} — manda
    un correo con la configuración guardada y dice si salió o qué falta.
    Sin destino, va al correo de quien lo pide.
    """

    permission_classes = [IS_SUPERADMIN]

    def post(self, request):
        from django.core.exceptions import ValidationError as ErrorDeValidacion
        from django.core.validators import validate_email

        from apps.common.correo import enviar_prueba

        destino = (request.data.get("destino") or request.user.email or "").strip()
        try:
            validate_email(destino)
        except ErrorDeValidacion:
            return Response({"detail": "Escribe un correo de destino válido."}, status=400)
        ok, texto = enviar_prueba(destino)
        _audit_platform(request, "test_email", "PlatformConfiguration",
                        PlatformConfiguration.get_solo().id, {"destino": destino, "ok": ok})
        return Response({"detail": texto}, status=200 if ok else 400)
