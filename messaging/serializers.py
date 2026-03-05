from rest_framework import serializers

from .models import WhatsAppMessage


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = WhatsAppMessage
        fields = [
            "id",
            "business",
            "invoice",
            "invoice_number",
            "phone_number",
            "message_text",
            "invoice_link",
            "delivery_status",
            "provider_message_id",
            "provider_response",
            "error_message",
            "sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SendWhatsAppInvoiceSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=20)
    message = serializers.CharField(required=False, allow_blank=True, default="")
