import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.funciones import funciones_de
from apps.accounts.models import (
    AuditLog,
    DeviceToken,
    OTPCode,
    PasswordResetToken,
    User,
)
from apps.accounts.preferencias import APARIENCIA, validar_apariencia
from apps.accounts.preferencias import CATALOGO as CATALOGO_PREFERENCIAS
from apps.accounts.preferencias import normalizar as normalizar_preferencias
from apps.accounts.serializers import (
    AuditLogSerializer,
    DeviceTokenSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    StaffLoginSerializer,
    StaffRecoveryConfirmSerializer,
    StaffRecoveryRequestSerializer,
    UserSerializer,
)
from apps.common.funcionalidades import activa
from apps.common.legal_views import condiciones_pendientes
from apps.common.permissions import HasRole
from apps.common.telefonos import normalizar_telefono
from apps.whatsapp.gateway_client import send_whatsapp_template

OTP_TTL_MINUTES = 5
RESET_TTL_MINUTES = 30


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class StaffLoginView(TokenObtainPairView):
    """POST /api/v1/auth/login/ — RF-USR-01"""

    serializer_class = StaffLoginSerializer


class OTPRequestView(APIView):
    """
    POST /api/v1/auth/otp/request/ — RF-USR-02, RF-WSP-01.

    Django decide *cuándo/qué* enviar; el microservicio FastAPI decide
    *cómo* llega a Meta (Arquitectura v1.2, sección 2).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = normalizar_telefono(serializer.validated_data["phone"])
        if not phone:
            return Response({"detail": "Escribe tu número de teléfono completo, por ejemplo 099 123 4567."},
                            status=status.HTTP_400_BAD_REQUEST)

        revisor = self._paciente_de_revision(phone)
        if revisor is not None:
            OTPCode.objects.create(
                user=revisor,
                code_hash=_hash_value(settings.APP_REVISION_CODIGO),
                purpose=OTPCode.Purpose.LOGIN,
                expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
            )
            logging.getLogger(__name__).info("Acceso de revisión de tienda usado (paciente %s).", revisor.id)
            return Response({"detail": "Código enviado por WhatsApp."}, status=status.HTTP_202_ACCEPTED)

        # Solo un número con acceso activado desde la ficha (ver
        # apps/patients/acceso_app.py). Antes se creaba una cuenta para
        # cualquier número —en la primera clínica— y se le enviaba un
        # WhatsApp: cualquiera podía gastar los mensajes de la clínica, y
        # el paciente real se quedaba con una cuenta «sin enlazar».
        user = (
            User.objects.filter(phone=phone, role=User.Role.PATIENT, is_active=True,
                                patient_profile__isnull=False)
            .select_related("tenant").first()
        )
        if user is None:
            return Response(
                {"detail": "Este número no tiene acceso a la app. Pide en la recepción de tu "
                           "clínica que lo activen en tu ficha."},
                status=status.HTTP_400_BAD_REQUEST)
        if not (user.tenant and user.tenant.is_active and activa(user.tenant, "app_paciente")):
            return Response(
                {"detail": "Tu clínica no tiene activa la app en este momento."},
                status=status.HTTP_400_BAD_REQUEST)
        self._issue_and_send_otp(user, phone, OTPCode.Purpose.LOGIN)
        return Response({"detail": "Código enviado por WhatsApp."}, status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _paciente_de_revision(phone):
        """
        El paciente de prueba para la revisión de las tiendas, si este es
        su teléfono y el acceso está configurado (APP_REVISION_* en
        settings). Solo una cuenta que ya existe: nunca crea ninguna.
        """
        telefono = normalizar_telefono(settings.APP_REVISION_TELEFONO)
        codigo = settings.APP_REVISION_CODIGO or ""
        if not telefono or not (len(codigo) == 6 and codigo.isdigit()) or phone != telefono:
            return None
        return User.objects.filter(phone=telefono, role=User.Role.PATIENT, is_active=True).first()

    @staticmethod
    def _issue_and_send_otp(user, phone, purpose):
        code = f"{secrets.randbelow(1_000_000):06d}"
        OTPCode.objects.create(
            user=user,
            code_hash=_hash_value(code),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
        )
        # Una sola plantilla: el paciente entra siempre con un código nuevo,
        # así que «recuperar el acceso» es lo mismo que volver a entrar.
        send_whatsapp_template(
            to_phone=phone,
            template_name="otp_login",
            language="es",
            variables={"1": code},
            patient_id=str(user.id),
        )


class OTPVerifyView(APIView):
    """POST /api/v1/auth/otp/verify/ — RF-USR-02"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = normalizar_telefono(serializer.validated_data["phone"])
        code = serializer.validated_data["code"]

        try:
            user = User.objects.get(phone=phone, role=User.Role.PATIENT, is_active=True)
        except User.DoesNotExist:
            return self._invalid()

        otp = (
            OTPCode.objects.filter(user=user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid or otp.code_hash != _hash_value(code):
            return self._invalid()

        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])
        # La ficha enseña «último ingreso a la app» con esto.
        user.last_login = otp.used_at
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        refresh["tenant_id"] = str(user.tenant_id)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "role": user.role}
        )

    @staticmethod
    def _invalid():
        return Response(
            {"detail": "Teléfono o código inválido."}, status=status.HTTP_400_BAD_REQUEST
        )


class StaffRecoveryRequestView(APIView):
    """POST /api/v1/auth/recovery/request/ — RF-USR-04 (staff, por correo)."""

    permission_classes = [permissions.AllowAny]
    # Mismo cupo que los códigos por WhatsApp: sin él, cualquiera podía
    # llenarle el buzón a una persona del personal pidiendo enlaces.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = StaffRecoveryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "Si el correo existe, recibirás instrucciones."})

        if user.role == User.Role.PATIENT:
            return Response({"detail": "Si el correo existe, recibirás instrucciones."})

        raw_token = secrets.token_urlsafe(32)
        PasswordResetToken.objects.create(
            user=user,
            token_hash=_hash_value(raw_token),
            expires_at=timezone.now() + timedelta(minutes=RESET_TTL_MINUTES),
        )
        # El correo lleva un enlace a la pantalla «Recuperar acceso» del
        # panel. Antes llevaba el código suelto —43 caracteres— y no había
        # ninguna pantalla donde escribirlo.
        # La respuesta es la misma pase lo que pase (no se revela si el
        # correo existe), pero un fallo de envío deja rastro.
        base = settings.PANEL_URL or request.build_absolute_uri("/").rstrip("/")
        enlace = f"{base}/recuperar/?token={raw_token}"
        saludo = f"Hola, {user.full_name}:" if user.full_name else "Hola:"
        try:
            send_mail(
                subject=f"Restablecer tu contraseña de {settings.MARCA}",
                message=(
                    f"{saludo}\n\n"
                    "Para elegir una contraseña nueva, abre este enlace:\n\n"
                    f"{enlace}\n\n"
                    f"El enlace es válido durante {RESET_TTL_MINUTES} minutos y se puede usar una sola vez.\n"
                    "Si no lo pediste tú, ignora este correo: tu contraseña no cambia.\n"
                ),
                from_email=None,
                recipient_list=[email],
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "No se pudo enviar el correo de recuperación (revisar EMAIL_HOST y compañía)",
                extra={"user_id": str(user.id)},
            )
        return Response({"detail": "Si el correo existe, recibirás instrucciones."})


class StaffRecoveryConfirmView(APIView):
    """POST /api/v1/auth/recovery/confirm/ — RF-USR-04."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StaffRecoveryConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        reset = (
            PasswordResetToken.objects.filter(
                token_hash=_hash_value(raw_token), used_at__isnull=True
            )
            .order_by("-created_at")
            .first()
        )
        if not reset or not reset.is_valid:
            return Response(
                {"detail": "El enlace de recuperación es inválido o expiró."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = reset.user
        # Las mismas reglas que al cambiarla desde el panel: sin esto, por
        # aquí se podía poner «clinica2026» o el propio correo.
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        # Elegida por la persona: si tenía una temporal, deja de tenerla.
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        # Todos sus enlaces pendientes dejan de valer, no solo este.
        PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        return Response({"detail": "Contraseña actualizada."})


class UserListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/users/ — RF-USR-03. Solo Admin gestiona staff."""

    serializer_class = UserSerializer
    permission_classes = [HasRole.for_roles("admin")]
    filterset_fields = ["role", "is_active"]

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.tenant).exclude(role=User.Role.PATIENT).order_by("email")

    def perform_create(self, serializer):
        user = serializer.save(tenant=self.request.tenant)
        _asegurar_ficha_de_doctor(self.request.tenant, user)


def _asegurar_ficha_de_doctor(tenant, user):
    """
    Un usuario con rol de doctor necesita su ficha `Doctor` para existir
    en la agenda y para que los actos clínicos queden atribuidos a
    alguien. Se crea si falta, tanto al dar de alta como al cambiar el
    rol.

    No se hace lo contrario —borrar la ficha al quitarle el rol— a
    propósito: de ella cuelgan citas e historia clínica, y perderlas por
    un cambio de puesto sería mucho peor que tener una ficha de más. Para
    eso está desactivarla.
    """
    if user.role != User.Role.DOCTOR:
        return
    from apps.agenda.models import Doctor

    Doctor.objects.get_or_create(tenant=tenant, user=user)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/users/{id}/ — incluye baja lógica (RF-USR-06)."""

    serializer_class = UserSerializer
    permission_classes = [HasRole.for_roles("admin")]

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        # La ficha de doctor se creaba solo al DAR DE ALTA el usuario, no
        # al cambiarle el rol después. Ascender a alguien a doctor lo
        # dejaba con rol de doctor en la lista de usuarios y sin ficha: no
        # salía en la agenda, no se le podía citar, y nada explicaba por
        # qué. Ahora se comprueba también aquí.
        user = serializer.save()
        _asegurar_ficha_de_doctor(self.request.tenant, user)


class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit-logs/ — RF-USR-05"""

    serializer_class = AuditLogSerializer
    permission_classes = [HasRole.for_roles("admin")]
    filterset_fields = ["user", "entity_type", "action"]

    def get_queryset(self):
        return AuditLog.objects.filter(tenant=self.request.tenant).order_by("-created_at")


class DeviceTokenRegisterView(generics.CreateAPIView):
    """POST /me/device-tokens/ — RF-APP-05"""

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # upsert: si el token ya existe, lo reactiva en vez de duplicar
        token = serializer.validated_data["fcm_token"]
        DeviceToken.objects.update_or_create(
            fcm_token=token,
            defaults={
                "user": self.request.user,
                "platform": serializer.validated_data["platform"],
                "is_active": True,
            },
        )


class MeView(APIView):
    """
    GET /api/v1/auth/me/ — perfil del usuario autenticado.
    El panel web lo usa tras el login para conocer nombre y rol
    (la navegación se filtra por rol en el cliente).
    """

    def get(self, request):
        u = request.user
        funciones = funciones_de(u)
        return Response({
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "must_change_password": u.must_change_password,
            # La administración de una clínica que no ha aceptado la
            # versión vigente de las condiciones va primero a aceptarlas.
            "condiciones_pendientes": condiciones_pendientes(u),
            # Funciones de gestión de esta persona. Las dos claves antiguas
            # se siguen dando, derivadas, para un panel en caché de antes.
            "funciones": funciones,
            "puede_gestionar_logros": funciones["logros"],
            "puede_gestionar_whatsapp": funciones["whatsapp"],
            # El panel esconde los módulos que la clínica no tiene. Es
            # cortesía: el candado de verdad está en la API, en
            # `RequiereFuncionalidad`.
            "funcionalidades": _funcionalidades_de(u),
            "preferencias": normalizar_preferencias(u.preferencias),
            # El panel lo enseña junto al nombre de la clínica: quien trabaja
            # en ella ve funciones que las demás todavía no tienen.
            "clinica_de_pruebas": bool(u.tenant_id and u.tenant.es_prueba),
        })


class CatalogoFuncionesView(APIView):
    """
    GET /api/v1/users/funciones/ — el catálogo de funciones para el alta
    de profesionales.

    El panel NO guarda su propia copia: la lista, los textos y lo que va
    marcado por defecto salen de aquí, así que no pueden desincronizarse.
    `disponible` dice si la clínica tiene contratada la funcionalidad de
    la que depende; si no, el panel la enseña desactivada.
    """

    permission_classes = [HasRole.for_roles("admin")]

    def get(self, request):
        from apps.accounts.funciones import AL_CREAR, CATALOGO, ROLES_CON_FUNCIONES
        from apps.common.funcionalidades import activa

        return Response([
            {
                "clave": clave,
                "etiqueta": d["etiqueta"],
                "descripcion": d["descripcion"],
                "disponible": d["funcionalidad"] is None or activa(request.tenant, d["funcionalidad"]),
                "al_crear": {rol: clave in AL_CREAR.get(rol, set()) for rol in ROLES_CON_FUNCIONES},
                "roles": list(d.get("roles", ROLES_CON_FUNCIONES)),
            }
            for clave, d in CATALOGO.items()
        ])


class PreferenciasView(APIView):
    """
    GET/PATCH /api/v1/auth/me/preferencias/ — las preferencias PROPIAS.

    No lleva identificador de usuario en la ruta a propósito: cada cual
    solo puede tocar las suyas, y así no hay ninguna forma de pedir las
    de otro. `disponibles` dice cuáles tienen efecto en su clínica, para
    que el panel pueda explicar por qué un interruptor no hace nada.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _respuesta(self, u):
        contratadas = _funcionalidades_de(u)
        return Response({
            "preferencias": normalizar_preferencias(u.preferencias),
            "disponibles": {
                clave: bool(contratadas.get(d["funcionalidad"], False))
                for clave, d in CATALOGO_PREFERENCIAS.items()
            },
        })

    def get(self, request):
        if request.user.role == User.Role.PATIENT:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return self._respuesta(request.user)

    def patch(self, request):
        u = request.user
        if u.role == User.Role.PATIENT:
            return Response(status=status.HTTP_403_FORBIDDEN)
        datos = dict(request.data) if isinstance(request.data, dict) else {}
        desconocidas = sorted(set(datos) - set(CATALOGO_PREFERENCIAS) - set(APARIENCIA))
        if desconocidas:
            return Response({"detail": f"Preferencias desconocidas: {', '.join(desconocidas)}."},
                            status=status.HTTP_400_BAD_REQUEST)
        no_booleanas = sorted(k for k, v in datos.items()
                              if k in CATALOGO_PREFERENCIAS and not isinstance(v, bool))
        if no_booleanas:
            return Response({"detail": f"Tienen que ser verdadero o falso: {', '.join(no_booleanas)}."},
                            status=status.HTTP_400_BAD_REQUEST)
        for clave in set(datos) & set(APARIENCIA):
            try:
                datos[clave] = validar_apariencia(clave, datos[clave])
            except ValueError as exc:
                return Response({"detail": f"{clave}: {exc}."}, status=status.HTTP_400_BAD_REQUEST)
        # Elegir tema propio es una función de la clínica (en prueba
        # mientras no se publique): sin ella, solo se puede volver al de la
        # clínica. Quitárselo siempre se puede.
        if datos.get("tema") and not _funcionalidades_de(u).get("temas_personales"):
            return Response(
                {"detail": "Tu clínica todavía no tiene la elección de tema por persona."},
                status=status.HTTP_403_FORBIDDEN)
        u.preferencias = {**normalizar_preferencias(u.preferencias), **datos}
        u.save(update_fields=["preferencias"])
        return self._respuesta(u)


def _funcionalidades_de(usuario):
    from apps.common.funcionalidades import CATALOGO, efectivas

    if usuario.tenant_id is None:
        # El Super Administrador opera sobre la plataforma, no dentro de
        # una clínica. Se le devuelve todo apagado para que el panel no
        # le pinte módulos de clínica que no le corresponden.
        return {clave: False for clave in CATALOGO}
    return efectivas(usuario.tenant)
