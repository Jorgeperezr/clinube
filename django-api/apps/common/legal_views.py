"""
Rutas de los textos legales (ver apps/common/legal.py).

  GET  /api/v1/legal/privacidad/          aviso de privacidad, público
  GET  /api/v1/legal/condiciones/         condiciones de uso, públicas
  POST /api/v1/legal/condiciones/aceptar/ la administración de la clínica
                                          acepta la versión vigente

Los textos son públicos a propósito: el aviso tiene que poder leerlo un
paciente antes de dar ningún dato, y las condiciones, quien todavía no
ha decidido si usar la plataforma.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.middleware import AuditLogMiddleware
from apps.accounts.models import AuditLog
from apps.common import legal
from apps.common.models import AceptacionCondiciones
from apps.common.permissions import HasRole


class _TextoPublico(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    # Sin el cupo de anónimo: alguien que pulsa «Aviso de privacidad» en
    # la pantalla de entrada después de equivocarse varias veces con la
    # contraseña no debería encontrarse un 429 en lugar del aviso. Es un
    # texto que sale de memoria y de una fila de configuración.
    throttle_classes = []


class AvisoPrivacidadView(_TextoPublico):
    def get(self, request):
        return Response(legal.aviso_privacidad())


class CondicionesView(_TextoPublico):
    def get(self, request):
        return Response(legal.condiciones())


def condiciones_pendientes(usuario):
    """¿Tiene esta persona que aceptar las condiciones antes de seguir?

    Solo la administración de una clínica puede aceptarlas, y basta con
    que lo haga una de sus administradoras: la que acepta lo hace en
    nombre de la clínica.
    """
    if getattr(usuario, "role", None) != "admin" or not usuario.tenant_id:
        return False
    return not AceptacionCondiciones.objects.filter(
        tenant_id=usuario.tenant_id, version=legal.CONDICIONES_VERSION
    ).exists()


class AceptarCondicionesView(APIView):
    permission_classes = [HasRole.for_roles("admin")]

    def post(self, request):
        if request.data.get("version") != legal.CONDICIONES_VERSION:
            # Quien tenía abierta una versión anterior no acepta la nueva
            # sin haberla visto.
            return Response(
                {"detail": "Las condiciones cambiaron mientras las leías. Vuelve a cargarlas."},
                status=status.HTTP_409_CONFLICT,
            )
        u = request.user
        aceptacion, creada = AceptacionCondiciones.objects.get_or_create(
            tenant=request.tenant, version=legal.CONDICIONES_VERSION,
            defaults={
                "aceptada_por": u,
                "nombre": u.full_name,
                "correo": u.email,
                "ip": AuditLogMiddleware._get_client_ip(request),
            },
        )
        if creada:
            AuditLog.objects.create(
                tenant=request.tenant, user=u, action="accept_terms",
                entity_type="AceptacionCondiciones", entity_id=str(aceptacion.id),
                metadata={"version": aceptacion.version},
            )
        return Response({
            "version": aceptacion.version,
            "aceptada_en": aceptacion.created_at,
            "aceptada_por": aceptacion.nombre,
        }, status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)
