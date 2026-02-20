import smtplib
import base64
import json
from socket import timeout as socket_timeout
from urllib import error as urlerror
from urllib import request as urlrequest

from django.core.mail import EmailMessage, get_connection
from django.conf import settings

from .utils import generate_invoice_pdf


class InvoiceEmailError(Exception):
    """Raised when invoice email delivery fails."""


def _send_via_resend(invoice, pdf_bytes):
    api_key = settings.RESEND_API_KEY
    if not api_key:
        raise InvoiceEmailError("Resend is enabled but RESEND_API_KEY is missing.")

    from_email = settings.RESEND_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL
    if not from_email:
        raise InvoiceEmailError("RESEND_FROM_EMAIL or DEFAULT_FROM_EMAIL must be configured.")

    payload = {
        "from": from_email,
        "to": [invoice.client_email],
        "subject": f"Invoice {invoice.invoice_number}",
        "text": f"Dear {invoice.client_name},\n\nPlease find your invoice attached.",
        "attachments": [
            {
                "filename": f"{invoice.invoice_number}.pdf",
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ],
    }

    req = urlrequest.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=settings.EMAIL_TIMEOUT) as resp:
            if resp.status >= 400:
                body = resp.read().decode("utf-8", errors="ignore")
                raise InvoiceEmailError(f"Resend API error {resp.status}: {body}")
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise InvoiceEmailError(f"Resend API error {exc.code}: {body}") from exc
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise InvoiceEmailError(f"Resend request failed: {exc}") from exc


def _send_via_smtp(invoice, pdf_bytes):
    email = EmailMessage(
        subject=f"Invoice {invoice.invoice_number}",
        body=f"Dear {invoice.client_name},\n\nPlease find your invoice attached.",
        to=[invoice.client_email],
        connection=get_connection(fail_silently=False),
    )

    email.attach(
        f"{invoice.invoice_number}.pdf",
        pdf_bytes,
        "application/pdf",
    )

    try:
        email.send(fail_silently=False)
    except (smtplib.SMTPException, socket_timeout, TimeoutError, OSError) as exc:
        raise InvoiceEmailError(str(exc)) from exc


def send_invoice_email(invoice):
    pdf = generate_invoice_pdf(invoice)
    pdf_bytes = pdf.read()

    provider = getattr(settings, "EMAIL_PROVIDER", "smtp").lower()
    if provider == "resend":
        _send_via_resend(invoice, pdf_bytes)
    else:
        _send_via_smtp(invoice, pdf_bytes)
