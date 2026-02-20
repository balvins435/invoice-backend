import smtplib
from socket import timeout as socket_timeout

from django.core.mail import EmailMessage, get_connection

from .utils import generate_invoice_pdf


class InvoiceEmailError(Exception):
    """Raised when invoice email delivery fails."""


def send_invoice_email(invoice):
    pdf = generate_invoice_pdf(invoice)

    email = EmailMessage(
        subject=f"Invoice {invoice.invoice_number}",
        body=f"Dear {invoice.client_name},\n\nPlease find your invoice attached.",
        to=[invoice.client_email],
        connection=get_connection(fail_silently=False),
    )

    email.attach(
        f"{invoice.invoice_number}.pdf",
        pdf.read(),
        "application/pdf",
    )

    try:
        email.send(fail_silently=False)
    except (smtplib.SMTPException, socket_timeout, TimeoutError, OSError) as exc:
        raise InvoiceEmailError(str(exc)) from exc
