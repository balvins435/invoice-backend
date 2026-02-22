from rest_framework import serializers
from .models import Invoice, InvoiceItem, Receipt, generate_invoice_number
from business.models import Business
from decimal import Decimal


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'total']


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            'id',
            'receipt_number',
            'payment_method',
            'payment_date',
            'amount_paid',
            'notes',
            'created_at',
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)
    has_receipt = serializers.SerializerMethodField()
    receipt_number = serializers.SerializerMethodField()
    business_id = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(),
        source='business'
    )

    class Meta:
        model = Invoice
        fields = [
            'id',
            'business_id',
            'invoice_number',
            'client_name',
            'client_email',
            'issue_date',
            'due_date',
            'subtotal',
            'tax_amount',
            'total_amount',
            'status',
            'items',
            'has_receipt',
            'receipt_number',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        invoice = Invoice.objects.create(**validated_data)

        for item in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item)

        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                InvoiceItem.objects.create(invoice=instance, **item)

        return instance
    
# invoice number generation

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        business = validated_data['business']

        invoice_number = generate_invoice_number(business)
        validated_data['invoice_number'] = invoice_number

        invoice = Invoice.objects.create(**validated_data)

        for item in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item)

        return invoice
    
# tax calculation
    def validate(self, data):
        items = data.get('items', [])
        business = data.get('business')

        subtotal = Decimal('0.00')
        for item in items:
            subtotal += Decimal(item['quantity']) * Decimal(item['unit_price'])

        tax_rate = business.tax_rate
        tax_amount = (subtotal * tax_rate) / Decimal('100')
        total_amount = subtotal + tax_amount

        data['subtotal'] = subtotal
        data['tax_amount'] = tax_amount
        data['total_amount'] = total_amount

        return data

    def get_has_receipt(self, obj):
        return obj.receipts.exists()

    def get_receipt_number(self, obj):
        receipt = obj.receipts.first()
        return receipt.receipt_number if receipt else None
