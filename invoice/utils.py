from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO


def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 800, invoice.business.name)

    p.setFont("Helvetica", 10)
    p.drawString(50, 780, f"Invoice: {invoice.invoice_number}")
    p.drawString(50, 760, f"Client: {invoice.client_name}")

    y = 720
    for item in invoice.items.all():
        p.drawString(50, y, item.description)
        p.drawRightString(550, y, f"{item.total}")
        y -= 20

    p.drawString(50, y - 20, f"Subtotal: {invoice.subtotal}")
    p.drawString(50, y - 40, f"VAT: {invoice.tax_amount}")
    p.drawString(50, y - 60, f"Total: {invoice.total_amount}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer
