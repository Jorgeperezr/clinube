"""
Entrar con Google.

El navegador (o la app) obtiene de Google un «ID token» firmado; aquí se
comprueba la firma con las claves públicas de Google, que el token sea
para NUESTRO ID de cliente, que no haya caducado y que Google haya
verificado el correo. Con eso, el correo es de quien entra.

    GET  /api/v1/auth/google/config/   {"client_id"} o vacío si no está configurado
    POST /api/v1/auth/google/          {"credential", "para": "personal"|"paciente"}

· Personal: tiene que existir ya una cuenta del equipo con ese correo (la
  da de alta su clínica). Google no crea personal.
· Paciente: si no tiene cuenta se crea una propia, sin clínica, igual que
  con el código por correo; su clínica la enlaza desde la ficha.

Se usa google-auth, que ya viene con django-storages[google]; las claves
se piden con httpx y se guardan una hora.
"""

import logging

import httpx
from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import acceso_paciente
from apps.accounts.models import AuditLog, User

logger = logging.getLogger(__name__)
CLAVES_URL = "https://www.googleapis.com/oauth2/v1/certs"
EMISORES = ("accounts.google.com", "https://accounts.google.com")


def client_id():
    from apps.common.models import PlatformConfiguration

    config = PlatformConfiguration.objects.first()
    return (getattr(config, "google_client_id", "") or "").strip()


def _claves():
    claves = cache.get("google_oauth_certs")
    if claves is None:
        r = httpx.get(CLAVES_URL, timeout=10)
        r.raise_for_status()
        claves = r.json()
        cache.set("google_oauth_certs", claves, 3600)
    return claves


def verificar(credencial, audiencia):
    """Los datos del token si es válido para `audiencia`; si no, ValueError."""
    from google.auth import jwt

    datos = jwt.decode(credencial, certs=_claves(), audience=audiencia)
    if datos.get("iss") not in EMISORES:
        raise ValueError("Emisor desconocido")
    if not datos.get("email") or datos.get("email_verified") not in (True, "true"):
        raise ValueError("Google no verificó ese correo")
    return datos


def _tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["tenant_id"] = str(user.tenant_id)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "role": user.role}


class GoogleConfigView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"client_id": client_id()})


class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        audiencia = client_id()
        if not audiencia:
            return Response({"detail": "Entrar con Google no está configurado en la plataforma."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            datos = verificar(str(request.data.get("credential") or ""), audiencia)
        except Exception:
            logger.info("Token de Google rechazado", exc_info=True)
            return Response({"detail": "Google no confirmó tu cuenta. Inténtalo de nuevo."},
                            status=status.HTTP_400_BAD_REQUEST)
        correo = acceso_paciente.normalizar_correo(datos["email"])

        if request.data.get("para") == "paciente":
            return self._paciente(correo, datos)
        return self._personal(correo)

    def _personal(self, correo):
        user = User.objects.filter(email__iexact=correo, is_active=True).exclude(role=User.Role.PATIENT).first()
        if user is None:
            return Response({"detail": f"No hay una cuenta del equipo con {correo}. Pide al administrador "
                                       "de tu clínica que te dé de alta con este correo."},
                            status=status.HTTP_400_BAD_REQUEST)
        if user.must_change_password:
            # La contraseña temporal la puso otra persona y quien entra ya
            # demostró con Google que el correo es suyo: se anula, en vez de
            # obligarle a elegir una que quizá no usará nunca.
            user.set_unusable_password()
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password"])
        AuditLog.objects.create(tenant=user.tenant, user=user, action="login_google",
                                entity_type="User", entity_id=str(user.id))
        return Response({**_tokens(user), "must_change_password": False})

    def _paciente(self, correo, datos):
        if User.objects.filter(email__iexact=correo).exclude(role=User.Role.PATIENT).exists():
            return Response({"detail": "Ese correo es de una cuenta del equipo de una clínica: "
                                       "entra con él en el panel, no en la app."},
                            status=status.HTTP_400_BAD_REQUEST)
        user, motivo = acceso_paciente.cuenta_por_correo(correo)
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)
        if user is None:
            user = acceso_paciente.crear_cuenta_propia(correo, datos.get("name") or "")
        return Response(_tokens(user))
