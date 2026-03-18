import json
import logging
from datetime import datetime
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from tax.models import TaxSubmission

logger = logging.getLogger(__name__)


class EtimsService:
    """Submit invoice payloads to KRA eTIMS and persist submission results."""

    def __init__(self):
        self.api_url = getattr(settings, "ETIMS_API_URL", "")
        self.api_key = getattr(settings, "ETIMS_API_KEY", "")
        self.timeout = getattr(settings, "ETIMS_TIMEOUT", 20)

    def _is_live_configured(self):
        return bool(self.api_url and self.api_key)

    def _build_payload(self, invoice):
        return {
            "invoiceNumber": invoice.invoice_number,
            "issueDate": invoice.issue_date.isoformat(),
            "dueDate": invoice.due_date.isoformat(),
            "client": {
                "name": invoice.client_name,
                "email": invoice.client_email,
            },
            "seller": {
                "name": invoice.business.name,
                "email": invoice.business.email,
                "phone": invoice.business.phone,
                "address": invoice.business.address,
            },
            "totals": {
                "subtotal": str(invoice.subtotal),
                "taxAmount": str(invoice.tax_amount),
                "totalAmount": str(invoice.total_amount),
            },
            "items": [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "unitPrice": str(item.unit_price),
                    "total": str(item.total),
                }
                for item in invoice.items.all()
            ],
        }

    def _submit_live(self, payload):
        req = request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _extract_tax_invoice_number(self, response_payload):
        return (
            response_payload.get("taxInvoiceNumber")
            or response_payload.get("invoiceNumber")
            or response_payload.get("data", {}).get("taxInvoiceNumber", "")
        )

    def submit_invoice(self, invoice, idempotency_key=None):
        if idempotency_key:
            existing = TaxSubmission.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing

        payload = self._build_payload(invoice)

        submission = TaxSubmission.objects.create(
            business=invoice.business,
            invoice=invoice,
            idempotency_key=idempotency_key,
            status=TaxSubmission.STATUS_PENDING,
            request_payload=payload,
        )

        if invoice.tax_invoice_number:
            submission.status = TaxSubmission.STATUS_SUBMITTED
            submission.tax_invoice_number = invoice.tax_invoice_number
            submission.response_payload = {
                "message": "Invoice already synced",
                "taxInvoiceNumber": invoice.tax_invoice_number,
            }
            submission.submitted_at = timezone.now()
            submission.save()
            return submission

        if not self._is_live_configured():
            tax_invoice_number = f"ETIMS-{datetime.now().strftime('%Y%m%d')}-{invoice.id}"
            submission.status = TaxSubmission.STATUS_SUBMITTED
            submission.tax_invoice_number = tax_invoice_number
            submission.response_payload = {
                "message": "Simulated eTIMS submission accepted.",
                "taxInvoiceNumber": tax_invoice_number,
            }
            submission.submitted_at = timezone.now()
            submission.save()

            invoice.tax_invoice_number = tax_invoice_number
            invoice.etims_synced_at = timezone.now()
            invoice.save(update_fields=["tax_invoice_number", "etims_synced_at"])
            return submission

        try:
            response_payload = self._submit_live(payload)
            tax_invoice_number = self._extract_tax_invoice_number(response_payload)

            if not tax_invoice_number:
                raise ValueError("eTIMS response did not include a tax invoice number")

            submission.status = TaxSubmission.STATUS_SUBMITTED
            submission.tax_invoice_number = tax_invoice_number
            submission.response_payload = response_payload
            submission.submitted_at = timezone.now()
            submission.save()

            invoice.tax_invoice_number = tax_invoice_number
            invoice.etims_synced_at = timezone.now()
            invoice.save(update_fields=["tax_invoice_number", "etims_synced_at"])

        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.exception("eTIMS submission failed for invoice=%s", invoice.id)
            submission.status = TaxSubmission.STATUS_FAILED
            submission.error_message = str(exc)
            submission.response_payload = {"error": str(exc)}
            submission.save(update_fields=["status", "error_message", "response_payload", "updated_at"])

        return submission
