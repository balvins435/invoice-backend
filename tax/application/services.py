from invoice.models import Invoice
from tax.models import TaxSubmission
from tax.services.etims_service import EtimsService

def idempotency_key_from(request):
    key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
    return (key or "").strip() or None

def find_replay(key, user):
    return TaxSubmission.objects.filter(idempotency_key=key, business__owner=user).select_related("invoice", "business").first()

def key_is_used(key): return TaxSubmission.objects.filter(idempotency_key=key).exists()

def find_invoice(invoice_id, user):
    return Invoice.objects.filter(id=invoice_id, business__owner=user).select_related("business").prefetch_related("items").first()

def submit_invoice(invoice, key): return EtimsService().submit_invoice(invoice, idempotency_key=key)
