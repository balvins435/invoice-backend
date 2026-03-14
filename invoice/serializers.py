from decimal import Decimal

from rest_framework import serializers
from django.db.models import Sum

from business.models import Business

from .models import Invoice, InvoiceItem, Receipt, generate_invoice_number


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
            "tax_invoice_number",
            "etims_synced_at",
            "status",
            "items",
            "has_receipt",
            "receipt_number",
            "amount_paid",
            "balance_due",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "subtotal",
            "tax_amount",
            "total_amount",
            "tax_invoice_number",
            "etims_synced_at",
            "created_at",
        ]

    def _compute_totals(self, items, business):
        subtotal = Decimal("0.00")
        for item in items:
            quantity = Decimal(str(item["quantity"]))
            unit_price = Decimal(str(item["unit_price"]))
            subtotal += quantity * unit_price

        tax_rate = Decimal(str(business.tax_rate)) if business else Decimal("0.00")
        tax_amount = (subtotal * tax_rate) / Decimal("100")
        total_amount = subtotal + tax_amount
        return subtotal, tax_amount, total_amount

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

        subtotal, tax_amount, total_amount = self._compute_totals(items, business)
        data["subtotal"] = subtotal
        data["tax_amount"] = tax_amount
        data["total_amount"] = total_amount
        return data

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        business = validated_data["business"]

        validated_data["invoice_number"] = generate_invoice_number(business)
        invoice = Invoice.objects.create(**validated_data)

        for item in items_data:
            total = Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
            InvoiceItem.objects.create(
                invoice=invoice,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total=total,
            )

        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                total = Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
                InvoiceItem.objects.create(
                    invoice=instance,
                    description=item["description"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    total=total,
                )

        return instance

    def get_has_receipt(self, obj):
        return obj.receipts.exists()

    def get_receipt_number(self, obj):
        receipt = obj.receipts.first()
        return receipt.receipt_number if receipt else None

    def get_amount_paid(self, obj):
        total = obj.receipts.aggregate(total=Sum("amount_paid")).get("total")
        return total or Decimal("0.00")

    def get_balance_due(self, obj):
        amount_paid = self.get_amount_paid(obj)
        balance = obj.total_amount - amount_paid
        return balance if balance > Decimal("0.00") else Decimal("0.00")
