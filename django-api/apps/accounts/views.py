import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts import acceso_paciente, atencion
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


class OTPCanalView(APIView):
    """
    GET /api/v1/auth/otp/canal/ — por dónde llega hoy el código: la app lo
    pregunta para pedir el teléfono («whatsapp») o el correo («correo»).
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"canal": acceso_paciente.canal_codigo()})


class OTPRequestView(APIView):
    """
    POST /api/v1/auth/otp/request/ — RF-USR-02, RF-WSP-01.

    El paciente manda {"phone": …} o {"email": …}; el código le llega por
    el canal que elija la plataforma (ver apps/accounts/acceso_paciente.py).
    Para WhatsApp, Django decide *cuándo/qué* enviar y el microservicio
    FastAPI *cómo* llega a Meta (Arquitectura v1.2, sección 2).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        canal = acceso_paciente.canal_codigo()

        revisor = self._paciente_de_revision(serializer.validated_data)
        if revisor is not None:
            OTPCode.objects.create(
                user=revisor,
                code_hash=_hash_value(settings.APP_REVISION_CODIGO),
                purpose=OTPCode.Purpose.LOGIN,
                expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
            )
            logging.getLogger(__name__).info("Acceso de revisión de tienda usado (paciente %s).", revisor.id)
            return Response({"detail": self._enviado(canal, revisor)}, status=status.HTTP_202_ACCEPTED)

        # Solo una cuenta con acceso activado desde la ficha (ver
        # apps/patients/acceso_app.py). Antes se creaba una cuenta para
        # cualquier número —en la primera clínica— y se le enviaba un
        # WhatsApp: cualquiera podía gastar los mensajes de la clínica, y
        # el paciente real se quedaba con una cuenta «sin enlazar».
        datos = serializer.validated_data
        user, motivo = acceso_paciente.identificar(datos)
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)
        if user is None and datos.get("email"):
            correo = acceso_paciente.normalizar_correo(datos["email"])
            if User.objects.filter(email__iexact=correo).exclude(role=User.Role.PATIENT).exists():
                return Response({"detail": "Ese correo es de una cuenta del equipo de una clínica: "
                                           "entra con él en el panel, no en la app."},
                                status=status.HTTP_400_BAD_REQUEST)
            if not datos.get("crear"):
                # La app ofrece crearla: el paciente la crea él mismo y
                # su clínica le da acceso a su ficha después.
                return Response({"detail": "Todavía no tienes cuenta con este correo. Créala en un "
                                           "momento: te enviamos un código para confirmar que es tuyo.",
                                 "puede_crear": True}, status=status.HTTP_400_BAD_REQUEST)
            user = acceso_paciente.crear_cuenta_propia(correo, datos.get("nombre"))
        if user is None:
            return Response(
                {"detail": "Este número no tiene acceso a la app. Entra con tu correo electrónico."},
                status=status.HTTP_400_BAD_REQUEST)
        if user.tenant_id and not (user.tenant.is_active and activa(user.tenant, "app_paciente")):
            return Response(
                {"detail": "Tu clínica no tiene activa la app en este momento."},
                status=status.HTTP_400_BAD_REQUEST)

        canal = acceso_paciente.canal_para(datos, user)
        if canal == acceso_paciente.CORREO and not acceso_paciente.correo_de(user):
            return Response(
                {"detail": "Tu ficha no tiene correo electrónico. Pide en la recepción de tu "
                           "clínica que lo añadan: el código llega por correo."},
                status=status.HTTP_400_BAD_REQUEST)

        if not self._issue_and_send_otp(user, canal):
            return Response(
                {"detail": "No se pudo enviar el correo con tu código. Inténtalo en unos minutos; "
                           "si sigue fallando, avisa a tu clínica."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": self._enviado(canal, user)}, status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _enviado(canal, user):
        if canal == acceso_paciente.CORREO:
            oculto = acceso_paciente.ocultar(acceso_paciente.correo_de(user))
            return (f"Te enviamos el código a {oculto}. Si no lo ves, mira en «Spam»."
                    if oculto else "Te enviamos el código por correo.")
        return "Código enviado por WhatsApp."

    @staticmethod
    def _paciente_de_revision(datos):
        """
        El paciente de prueba para la revisión de las tiendas, si se
        identifica con su teléfono o su correo y el acceso está configurado
        (APP_REVISION_* en settings). Solo una cuenta que ya existe: nunca
        crea ninguna.
        """
        telefono = normalizar_telefono(settings.APP_REVISION_TELEFONO)
        codigo = settings.APP_REVISION_CODIGO or ""
        if not telefono or not (len(codigo) == 6 and codigo.isdigit()):
            return None
        revisor = User.objects.filter(phone=telefono, role=User.Role.PATIENT, is_active=True).first()
        if revisor is None:
            return None
        if datos.get("email"):
            correo = acceso_paciente.normalizar_correo(datos["email"])
            return revisor if correo and correo == acceso_paciente.correo_de(revisor) else None
        return revisor if normalizar_telefono(datos.get("phone") or "") == telefono else None

    @staticmethod
    def _issue_and_send_otp(user, canal):
        """Crea el código y lo manda. False si el correo no salió."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        otp = OTPCode.objects.create(
            user=user,
            code_hash=_hash_value(code),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
        )
        if canal == acceso_paciente.CORREO:
            try:
                acceso_paciente.enviar_codigo_por_correo(user, code, OTP_TTL_MINUTES)
            except Exception:
                logging.getLogger(__name__).exception(
                    "No se pudo enviar el código por correo (revisar el correo en Plataforma)",
                    extra={"user_id": str(user.id)},
                )
                # Un código que no llegó no debe quedar vivo.
                otp.delete()
                return False
            return True
        # Una sola plantilla: el paciente entra siempre con un código nuevo,
        # así que «recuperar el acceso» es lo mismo que volver a entrar.
        send_whatsapp_template(
            to_phone=user.phone,
            template_name="otp_login",
            language="es",
            variables={"1": code},
            patient_id=str(user.id),
        )
        return True


class OTPVerifyView(APIView):
    """POST /api/v1/auth/otp/verify/ — RF-USR-02. Teléfono o correo, y el código."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        user, _motivo = acceso_paciente.identificar(serializer.validated_data)
        if user is None and not serializer.validated_data.get("email"):
            # El revisor de las tiendas puede no tener ficha enlazada.
            telefono = normalizar_telefono(serializer.validated_data.get("phone") or "")
            user = User.objects.filter(phone=telefono, role=User.Role.PATIENT,
                                       is_active=True).first() if telefono else None
        por_correo = bool(serializer.validated_data.get("email"))
        if user is None:
            return self._invalid(por_correo)

        otp = (
            OTPCode.objects.filter(user=user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid or otp.code_hash != _hash_value(code):
            return self._invalid(por_correo)

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
    def _invalid(por_correo=False):
        dato = "Correo" if por_correo else "Teléfono"
        return Response(
            {"detail": f"{dato} o código inválido."}, status=status.HTTP_400_BAD_REQUEST
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
        try:
            from apps.accounts.correos_personal import enviar_recuperacion

            enviar_recuperacion(user, enlace, RESET_TTL_MINUTES)
        except Exception:
            logging.getLogger(__name__).exception(
                "No se pudo enviar el correo de recuperación (revisar el correo en Plataforma → Configuración o EMAIL_HOST)",
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
        # Sin contraseña puesta por el administrador, la persona recibe una
        # invitación con la marca de la clínica para elegir la suya (o
        # entrar con Google). Nadie más llega a conocer su contraseña.
        self._invitacion = invitar(self.request, user) if not user.has_usable_password() else None

    def create(self, request, *args, **kwargs):
        self._invitacion = None
        respuesta = super().create(request, *args, **kwargs)
        respuesta.data["invitacion"] = self._invitacion
        return respuesta


INVITACION_HORAS = 72


def enlace_de_bienvenida(request, user):
    """Enlace de un solo uso para que la persona elija su primera contraseña."""
    raw_token = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(
        user=user, token_hash=_hash_value(raw_token),
        expires_at=timezone.now() + timedelta(hours=INVITACION_HORAS),
    )
    base = settings.PANEL_URL or request.build_absolute_uri("/").rstrip("/")
    return f"{base}/recuperar/?token={raw_token}&bienvenida=1"


def invitar(request, user):
    """Manda la invitación y dice cómo fue: «enviada» o «fallo»."""
    from apps.accounts.correos_personal import enviar_invitacion
    from apps.accounts.google import client_id

    enlace = enlace_de_bienvenida(request, user)
    try:
        enviar_invitacion(user, enlace, INVITACION_HORAS, con_google=bool(client_id()))
    except Exception:
        logging.getLogger(__name__).exception("No se pudo enviar la invitación", extra={"user_id": str(user.id)})
        return "fallo"
    AuditLog.objects.create(tenant=user.tenant, user=request.user, action="invite_staff",
                            entity_type="User", entity_id=str(user.id))
    return "enviada"


class InvitarUsuarioView(APIView):
    """POST /api/v1/users/{id}/invitar/ — vuelve a mandar la invitación."""

    permission_classes = [HasRole.for_roles("admin")]

    def post(self, request, pk):
        user = generics.get_object_or_404(
            User.objects.exclude(role=User.Role.PATIENT), pk=pk, tenant=request.tenant, is_active=True)
        if not user.email:
            return Response({"detail": "Esta persona no tiene correo."}, status=status.HTTP_400_BAD_REQUEST)
        resultado = invitar(request, user)
        if resultado == "fallo":
            return Response({"detail": "No se pudo enviar el correo. Revisa el correo saliente en Plataforma."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"invitacion": resultado})


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
        return AuditLog.objects.filter(tenant=self.request.tenant).select_related("user").order_by("-created_at")


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
            # Si además de su rol atiende pacientes (el administrador de un
            # consultorio): el panel le enseña «Mi firma» y su agenda.
            "atiende": u.role == User.Role.DOCTOR or atencion.atiende(u),
            "modalidad": u.tenant.modalidad if u.tenant_id else None,
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
