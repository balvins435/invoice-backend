import smtplib
import base64
import json
from socket import timeout as socket_timeout
from urllib import error as urlerror
from urllib import request as urlrequest

from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings
from django.template.loader import render_to_string

from .utils import generate_invoice_pdf


class InvoiceEmailError(Exception):
    """Raised when invoice email delivery fails."""


def _build_invoice_email_content(invoice):
    context = {
        "invoice": invoice,
        "business": invoice.business,
    }
    subject = f"Invoice {invoice.invoice_number} from {invoice.business.name}"
    text_content = render_to_string("emails/invoice_email.txt", context)
    html_content = render_to_string("emails/invoice_email.html", context)
    return subject, text_content, html_content


def _send_via_sendgrid(invoice, pdf_bytes):
    api_key = settings.SENDGRID_API_KEY
    if not api_key:
        raise InvoiceEmailError("SendGrid is enabled but SENDGRID_API_KEY is missing.")

    from_email = settings.SENDGRID_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL
    if not from_email:
        raise InvoiceEmailError("SENDGRID_FROM_EMAIL or DEFAULT_FROM_EMAIL must be configured.")

    subject, text_content, html_content = _build_invoice_email_content(invoice)

    payload = {
        "from": {"email": from_email},
        "personalizations": [
            {
                "to": [{"email": invoice.client_email}],
                "subject": subject,
            }
        ],
        "reply_to": {"email": from_email},
        "headers": {
            "X-Auto-Response-Suppress": "All",
        },
        "content": [
            {
                "type": "text/plain",
                "value": text_content,
            },
            {
                "type": "text/html",
                "value": html_content,
            }
        ],
        "attachments": [
            {
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
                "type": "application/pdf",
                "filename": f"{invoice.invoice_number}.pdf",
                "disposition": "attachment",
            }
        ],
    }

    req = urlrequest.Request(
        "https://api.sendgrid.com/v3/mail/send",
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
                raise InvoiceEmailError(f"SendGrid API error {resp.status}: {body}")
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise InvoiceEmailError(f"SendGrid API error {exc.code}: {body}") from exc
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise InvoiceEmailError(f"SendGrid request failed: {exc}") from exc


def _send_via_smtp(invoice, pdf_bytes):
    subject, text_content, html_content = _build_invoice_email_content(invoice)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        to=[invoice.client_email],
        connection=get_connection(fail_silently=False),
        headers={
            "X-Auto-Response-Suppress": "All",
        },
    )
    email.attach_alternative(html_content, "text/html")

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
    if provider == "sendgrid":
        _send_via_sendgrid(invoice, pdf_bytes)
    else:
        _send_via_smtp(invoice, pdf_bytes)
