from rest_framework import serializers

from business.models import Business


class AIAssistantRequestSerializer(serializers.Serializer):
    MODE_AUTO = "auto"
    MODE_INVOICE = "invoice"
    MODE_REPORT = "report"
    MODE_GENERAL = "general"

    MODE_CHOICES = (
        (MODE_AUTO, "Auto"),
        (MODE_INVOICE, "Invoice"),
        (MODE_REPORT, "Report"),
        (MODE_GENERAL, "General"),
    )

    prompt = serializers.CharField(max_length=4000, trim_whitespace=True)
    mode = serializers.ChoiceField(choices=MODE_CHOICES, default=MODE_AUTO)
    business_id = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_business_id(self, business):
        request = self.context.get("request")
        if business and request and business.owner_id != request.user.id:
            raise serializers.ValidationError("Invalid business for this user.")
        return business


class GenerateInvoiceRequestSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=4000, trim_whitespace=True)
