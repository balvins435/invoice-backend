from rest_framework import serializers

from business.models import Business

from .application.pricing import calculate_invoice_totals
from .application.services import create_invoice, update_invoice
from .models import Invoice, InvoiceItem, Receipt


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["id", "description", "quantity", "unit_price", "total"]
        read_only_fields = ["id", "total"]


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            "id",
            "receipt_number",
            "payment_method",
            "payment_date",
            "amount_paid",
            "currency",
            "reference",
            "notes",
            "created_at",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)
    has_receipt = serializers.SerializerMethodField()
    receipt_number = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()
    business_id = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all(), source="business")

    # The create form intentionally allows invoices without a client email.
    # Keep that existing product behavior explicit at the API boundary.
    client_email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "business_id",
            "invoice_number",
            "client_name",
            "client_email",
            "issue_date",
            "due_date",
            "subtotal",
            "tax_amount",
            "total_amount",
            "currency",
            "template",
            "tax_invoice_number",
            "etims_synced_at",
            "status",
            "paid_at",
            "items",
            "has_receipt",
            "receipt_number",
            "amount_paid",
            "balance_due",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "subtotal",
            "tax_amount",
            "total_amount",
            "tax_invoice_number",
            "etims_synced_at",
            "paid_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        items = data.get("items")
        business = data.get("business")
        request = self.context.get("request")

        if self.instance:
            if items is None:
                items = [
                    {
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                    }
                    for item in self.instance.items.all()
                ]
            if business is None:
                business = self.instance.business

        if not business:
            raise serializers.ValidationError({"business_id": "This field is required."})
        if request and business.owner_id != request.user.id:
            raise serializers.ValidationError({"business_id": "You do not have access to this business."})
        if items is None:
            raise serializers.ValidationError({"items": "This field is required."})

        totals = calculate_invoice_totals(items, business.tax_rate)
        data["subtotal"] = totals.subtotal
        data["tax_amount"] = totals.tax_amount
        data["total_amount"] = totals.total_amount
        return data

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        return create_invoice(validated_data=validated_data, items_data=items_data)

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        return update_invoice(invoice=instance, validated_data=validated_data, items_data=items_data)

    def get_has_receipt(self, obj):
        return obj.receipts.exists()

    def get_receipt_number(self, obj):
        receipt = obj.receipts.first()
        return receipt.receipt_number if receipt else None

    def get_amount_paid(self, obj):
        return obj.amount_paid

    def get_balance_due(self, obj):
        return obj.balance_due
