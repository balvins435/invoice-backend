from invoice.models import Invoice
from messaging.models import WhatsAppMessage
from messaging.services.whatsapp_service import WhatsAppService

def idempotency_key_from(request):
    key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
    return (key or "").strip() or None

def find_replay(key, user):
    return WhatsAppMessage.objects.filter(idempotency_key=key, business__owner=user).select_related("invoice", "business").first()

def key_is_used(key): return WhatsAppMessage.objects.filter(idempotency_key=key).exists()

def find_invoice(invoice_id, user):
    return Invoice.objects.filter(id=invoice_id, business__owner=user).select_related("business").prefetch_related("items").first()

def send_invoice_message(*, invoice, phone_number, request, custom_message, idempotency_key):
    message = WhatsAppService().send_invoice(invoice=invoice, phone_number=phone_number, request_obj=request, custom_message=custom_message, idempotency_key=idempotency_key)
    if message.delivery_status == WhatsAppMessage.STATUS_SENT and invoice.status == "draft":
        invoice.status = "sent"
        invoice.save(update_fields=["status"])
    return message
