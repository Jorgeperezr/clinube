from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasRole
from apps.whatsapp.models import WhatsAppOptIn, WhatsAppTemplate
from apps.whatsapp.serializers import (
    WhatsAppOptInSerializer,
    WhatsAppTemplateSerializer,
)

CAN_MANAGE = HasRole.for_roles("admin")
CAN_MANAGE_OPTIN = HasRole.for_roles("admin", "reception")


class WhatsAppTemplateListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/config/whatsapp-templates/ — RN-WSP-01."""

    serializer_class = WhatsAppTemplateSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return WhatsAppTemplate.objects.filter(tenant=self.request.tenant).order_by("name")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class WhatsAppOptInListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/patients/{id}/whatsapp-optin/ — RN-WSP-02.

    Sin una autorización activa no sale ningún recordatorio por WhatsApp
    (ver apps/whatsapp/tasks.py): se registra desde la ficha del paciente.
    """

    serializer_class = WhatsAppOptInSerializer
    permission_classes = [CAN_MANAGE_OPTIN]

    def _paciente(self):
        from apps.patients.models import Patient

        # Antes se guardaba el id de la URL tal cual: una clínica podía
        # registrar autorizaciones a nombre de pacientes de otra.
        return generics.get_object_or_404(Patient, pk=self.kwargs["pk"], tenant=self.request.tenant)

    def get_queryset(self):
        return WhatsAppOptIn.objects.filter(
            patient=self._paciente(), tenant=self.request.tenant
        ).order_by("-opted_in_at")

    def create(self, request, *args, **kwargs):
        paciente = self._paciente()
        # Registrarla otra vez no crea una segunda autorización activa.
        activa = WhatsAppOptIn.objects.filter(
            patient=paciente, tenant=request.tenant, revoked_at__isnull=True
        ).first()
        if activa:
            return Response(WhatsAppOptInSerializer(activa).data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant=request.tenant, patient=paciente)
        return Response(serializer.data, status=201)


class WhatsAppOptInRevokeView(APIView):
    """POST /api/v1/whatsapp-optin/{id}/revoke/ — revoca el consentimiento."""

    permission_classes = [CAN_MANAGE_OPTIN]

    def post(self, request, pk):
        from django.utils import timezone

        optin = generics.get_object_or_404(
            WhatsAppOptIn, pk=pk, tenant=request.tenant
        )
        optin.revoked_at = timezone.now()
        optin.save(update_fields=["revoked_at"])
        return Response(WhatsAppOptInSerializer(optin).data)
