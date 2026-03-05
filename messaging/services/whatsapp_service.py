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
            delivery_status=WhatsAppMessage.STATUS_PENDING,
        )

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
                logger.exception("Twilio WhatsApp send failed for invoice=%s", invoice.id)
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
