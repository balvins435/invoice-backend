import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from invoice.models import Invoice
from messaging.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Invoice)
def auto_send_whatsapp_on_paid(sender, instance, **kwargs):
    """
    Auto-send WhatsApp notification when an invoice is paid.

    Retry-safe behavior is handled by idempotency_key in WhatsAppMessage.
    """
    if instance.status != "paid":
        return

    try:
        WhatsAppService().send_paid_invoice_notification(instance)
    except Exception:  # pragma: no cover - defensive logging for async-safe hook
        logger.exception("Auto WhatsApp notification failed for invoice=%s", instance.id)
