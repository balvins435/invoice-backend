from django.core.mail import EmailMessage
from .utils import generate_invoice_pdf

def send_invoice_email(invoice):
    pdf = generate_invoice_pdf(invoice)

    email = EmailMessage(
        subject=f"Invoice {invoice.invoice_number}",
        body=f"Dear {invoice.client_name},\n\nPlease find your invoice attached.",
        to=[invoice.client_email]
    )

    email.attach(
        f"{invoice.invoice_number}.pdf",
        pdf.read(),
        'application/pdf'
    )

    email.send()
