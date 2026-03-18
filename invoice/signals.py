from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Receipt


def _reconcile_invoice_status(invoice):
    total_paid = (
        Receipt.objects.filter(invoice=invoice)
        .aggregate(total=Sum("amount_paid"))
        .get("total")
        or Decimal("0.00")
    )

    updates = {}
    if total_paid >= invoice.total_amount:
        if invoice.status != "paid":
            updates["status"] = "paid"
        if not invoice.paid_at:
            updates["paid_at"] = timezone.now()
    elif invoice.status == "paid":
        # If receipts are removed/edited below the invoice amount, fall back to sent.
        updates["status"] = "sent"
        updates["paid_at"] = None

    if updates:
        for field, value in updates.items():
            setattr(invoice, field, value)
        invoice.save(update_fields=list(updates.keys()))


@receiver(post_save, sender=Receipt)
def reconcile_invoice_status_on_receipt_save(sender, instance, **kwargs):
    _reconcile_invoice_status(instance.invoice)


@receiver(post_delete, sender=Receipt)
def reconcile_invoice_status_on_receipt_delete(sender, instance, **kwargs):
    _reconcile_invoice_status(instance.invoice)
