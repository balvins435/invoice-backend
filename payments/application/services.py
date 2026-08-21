from invoice.models import Invoice
from payments.models import PaymentTransaction
from payments.services.mpesa_service import MpesaService


def idempotency_key_from(request):
    key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
    return (key or "").strip() or None


def find_replay(*, key, user):
    return PaymentTransaction.objects.filter(idempotency_key=key, business__owner=user).select_related("invoice", "business").first()


def idempotency_key_is_used(key):
    return PaymentTransaction.objects.filter(idempotency_key=key).exists()


def find_invoice(*, invoice_id, user):
    return Invoice.objects.filter(id=invoice_id, business__owner=user).select_related("business").first()


def initiate_payment(*, invoice, phone_number, amount, idempotency_key):
    return MpesaService().initiate_stk_push(invoice=invoice, phone_number=phone_number, amount=amount, idempotency_key=idempotency_key)
