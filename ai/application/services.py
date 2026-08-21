from business.models import Business
from ai.services.invoice_ai import generate_assistant_response, generate_invoice_from_text

def assistant_response(*, prompt, mode, business, user, report_mode, generator=generate_assistant_response):
    if not business and mode == report_mode:
        business = Business.objects.filter(owner=user).order_by("id").first()
        if business is None: return None
    return generator(prompt=prompt, business=business, mode=mode)

def invoice_from_text(text, generator=generate_invoice_from_text): return generator(text)
