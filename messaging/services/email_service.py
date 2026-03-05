from invoice.email_utils import send_invoice_email


def send_invoice_via_email(invoice):
    """Messaging app helper that delegates to existing invoice email utility."""
    return send_invoice_email(invoice)
