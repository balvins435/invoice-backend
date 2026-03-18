from rest_framework import serializers

from .models import PaymentTransaction
from .services.mpesa_service import MpesaService


class PaymentTransactionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "idempotency_key",
            "reference",
            "business",
            "invoice",
            "invoice_number",
            "phone_number",
            "amount",
            "currency",
            "status",
            "merchant_request_id",
            "checkout_request_id",
            "mpesa_receipt_number",
            "result_code",
            "result_description",
            "raw_request",
            "raw_response",
            "callback_payload",
            "paid_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class STKPushRequestSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def validate_phone_number(self, value):
        try:
            return MpesaService.normalize_msisdn(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class ManualConfirmationSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    result_code = serializers.CharField(max_length=20, required=False, default="0")
    result_description = serializers.CharField(required=False, allow_blank=True, default="Confirmed manually")
    mpesa_receipt_number = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
