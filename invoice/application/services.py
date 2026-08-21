from django.db import IntegrityError, transaction
from django.utils import timezone

from business.models import Business

from invoice.email_utils import send_invoice_email
from invoice.models import Invoice, InvoiceItem, Receipt, generate_invoice_number

from .pricing import calculate_item_total


def _create_items(invoice, items_data):
    InvoiceItem.objects.bulk_create(
        [
            InvoiceItem(
                invoice=invoice,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total=calculate_item_total(item),
            )
            for item in items_data
        ]
    )


@transaction.atomic
def create_invoice(*, validated_data, items_data):
    business = validated_data["business"]
    Business.objects.select_for_update().get(pk=business.pk)
    for attempt in range(3):
        validated_data["invoice_number"] = generate_invoice_number(business)
        try:
            invoice = Invoice.objects.create(**validated_data)
            break
        except IntegrityError:
            if attempt == 2:
                raise
    _create_items(invoice, items_data)
    return invoice


@transaction.atomic
def update_invoice(*, invoice, validated_data, items_data=None):
    for attribute, value in validated_data.items():
        setattr(invoice, attribute, value)
    invoice.save()
    if items_data is not None:
        invoice.items.all().delete()
        _create_items(invoice, items_data)
    return invoice


def _receipt_defaults(invoice, notes):
    return {
        "payment_method": "bank_transfer",
        "payment_date": timezone.localdate(),
        "amount_paid": invoice.total_amount,
        "currency": invoice.currency,
        "reference": f"manual-{invoice.invoice_number}",
        "notes": notes,
    }


@transaction.atomic
def mark_invoice_paid(invoice):
    if invoice.status != "paid":
        invoice.status = "paid"
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at"])
    receipt, _ = Receipt.objects.get_or_create(
        invoice=invoice,
        defaults=_receipt_defaults(
            invoice,
            "Auto-generated when invoice was marked as paid.",
        ),
    )
    return receipt


@transaction.atomic
def get_or_create_receipt(invoice):
    receipt = invoice.receipts.first()
    return receipt or Receipt.objects.create(
        invoice=invoice,
        **_receipt_defaults(
            invoice,
            "Auto-generated for an already paid invoice.",
        ),
    )


def send_invoice(invoice):
    send_invoice_email(invoice)
    invoice.status = "sent"
    invoice.save()
