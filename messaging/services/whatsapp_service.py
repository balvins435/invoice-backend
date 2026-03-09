import base64
import json
import logging
from urllib import parse, request

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from invoice.models import Invoice
from messaging.models import WhatsAppMessage
from payments.models import PaymentTransaction

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self):
        self.provider = getattr(settings, "WHATSAPP_PROVIDER", "mock").lower()
        self.twilio_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        self.twilio_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        self.twilio_from = getattr(settings, "TWILIO_WHATSAPP_FROM", "")
        self.backend_base_url = getattr(settings, "BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")

    @staticmethod
    def _normalize_phone(phone_number):
        phone = phone_number.strip()
        if phone.startswith("whatsapp:"):
            return phone
        return f"whatsapp:{phone}"

    @staticmethod
    def generate_invoice_token(invoice_id):
        signer = signing.TimestampSigner(salt="whatsapp-invoice")
        return signer.sign(str(invoice_id))

    @staticmethod
    def resolve_invoice_from_token(token, max_age_seconds):
        signer = signing.TimestampSigner(salt="whatsapp-invoice")
        invoice_id = signer.unsign(token, max_age=max_age_seconds)
        return Invoice.objects.select_related("business").prefetch_related("items").get(id=invoice_id)

    def build_invoice_link(self, invoice, request_obj=None):
        token = self.generate_invoice_token(invoice.id)
        path = reverse("messaging-public-invoice-pdf", kwargs={"token": token})
        if request_obj:
            return request_obj.build_absolute_uri(path)
        return f"{self.backend_base_url}{path}"

    def _send_twilio(self, to_phone, message_text):
        endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
        payload = parse.urlencode(
            {
                "To": self._normalize_phone(to_phone),
                "From": self._normalize_phone(self.twilio_from),
                "Body": message_text,
            }
        ).encode("utf-8")

        credentials = base64.b64encode(f"{self.twilio_sid}:{self.twilio_token}".encode("utf-8")).decode("utf-8")
        req = request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def send_invoice(self, invoice, phone_number, request_obj=None, custom_message=""):
        invoice_link = self.build_invoice_link(invoice, request_obj=request_obj)
        message_body = custom_message.strip() or (
            f"Hello {invoice.client_name}, your invoice {invoice.invoice_number} is ready. "
            f"View and download it here: {invoice_link}"
        )

        message = WhatsAppMessage.objects.create(
            business=invoice.business,
            invoice=invoice,
            phone_number=phone_number,
            invoice_link=invoice_link,
            message_text=message_body,
            message_type=WhatsAppMessage.TYPE_MANUAL_INVOICE,
            delivery_status=WhatsAppMessage.STATUS_PENDING,
        )
        return self._dispatch_message(message, phone_number, message_body)

    def _dispatch_message(self, message, phone_number, message_body):
        message.attempt_count += 1
        message.delivery_status = WhatsAppMessage.STATUS_PENDING
        message.error_message = ""
        message.save(update_fields=["attempt_count", "delivery_status", "error_message", "updated_at"])

        if self.provider == "twilio" and self.twilio_sid and self.twilio_token and self.twilio_from:
            try:
                provider_response = self._send_twilio(phone_number, message_body)
                message.provider_message_id = provider_response.get("sid", "")
                message.provider_response = provider_response
                message.delivery_status = WhatsAppMessage.STATUS_SENT
                message.sent_at = timezone.now()
                message.save()
                return message
            except Exception as exc:  # pragma: no cover - network/provider dependent
                logger.exception("Twilio WhatsApp send failed for invoice=%s", message.invoice_id)
                message.delivery_status = WhatsAppMessage.STATUS_FAILED
                message.error_message = str(exc)
                message.provider_response = {"error": str(exc)}
                message.save()
                return message

        message.provider_message_id = f"mock-{message.id}"
        message.provider_response = {"message": "Simulated WhatsApp message sent."}
        message.delivery_status = WhatsAppMessage.STATUS_SENT
        message.sent_at = timezone.now()
        message.save(update_fields=[
            "provider_message_id",
            "provider_response",
            "delivery_status",
            "sent_at",
            "updated_at",
        ])
        return message

    @staticmethod
    def _resolve_paid_invoice_phone(invoice):
        tx = invoice.payment_transactions.filter(
            status=PaymentTransaction.STATUS_COMPLETED
        ).order_by("-paid_at", "-created_at").first()
        return tx.phone_number if tx else ""

    def send_paid_invoice_notification(self, invoice):
        idempotency_key = f"paid-invoice-{invoice.id}"
        phone_number = self._resolve_paid_invoice_phone(invoice)
        invoice_link = self.build_invoice_link(invoice)
        message_body = (
            f"Payment received for invoice {invoice.invoice_number}. "
            f"Thank you {invoice.client_name}. View your invoice here: {invoice_link}"
        )

        message, _ = WhatsAppMessage.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "business": invoice.business,
                "invoice": invoice,
                "phone_number": phone_number,
                "invoice_link": invoice_link,
                "message_text": message_body,
                "message_type": WhatsAppMessage.TYPE_AUTO_PAID,
                "delivery_status": WhatsAppMessage.STATUS_PENDING,
            },
        )

        if message.delivery_status == WhatsAppMessage.STATUS_SENT:
            return message

        if not phone_number:
            message.delivery_status = WhatsAppMessage.STATUS_FAILED
            message.error_message = (
                "Auto-paid WhatsApp skipped: no completed payment phone number found."
            )
            message.provider_response = {"error": "missing_customer_phone"}
            message.attempt_count += 1
            message.save(update_fields=[
                "delivery_status",
                "error_message",
                "provider_response",
                "attempt_count",
                "updated_at",
            ])
            return message

        message.phone_number = phone_number
        message.invoice_link = invoice_link
        message.message_text = message_body
        message.message_type = WhatsAppMessage.TYPE_AUTO_PAID
        message.save(update_fields=["phone_number", "invoice_link", "message_text", "message_type", "updated_at"])

        return self._dispatch_message(message, phone_number, message_body)
