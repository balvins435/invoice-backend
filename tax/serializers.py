from rest_framework import serializers

from .models import TaxSubmission


class TaxSubmissionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = TaxSubmission
        fields = [
            "id",
            "business",
            "invoice",
            "invoice_number",
            "status",
            "tax_invoice_number",
            "request_payload",
            "response_payload",
            "error_message",
            "submitted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TaxSubmitRequestSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
