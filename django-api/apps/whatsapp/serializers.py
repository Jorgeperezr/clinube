from rest_framework import serializers

from apps.whatsapp.models import WhatsAppOptIn, WhatsAppTemplate


class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppTemplate
        fields = [
            "id", "name", "meta_template_name", "category",
            "language", "variables", "is_active",
        ]
        read_only_fields = ["id"]


class WhatsAppOptInSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = WhatsAppOptIn
        fields = ["id", "patient", "channel", "opted_in_at", "revoked_at", "is_active"]
        # El paciente sale de la URL (/patients/<id>/whatsapp-optin/), no
        # del cuerpo: pedirlo dos veces solo servía para que no coincidieran.
        read_only_fields = ["id", "patient", "opted_in_at", "revoked_at", "is_active"]
