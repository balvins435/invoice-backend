import logging
import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

PAGE_MARGIN = 18 * mm
CONTENT_WIDTH = A4[0] - (PAGE_MARGIN * 2)

BRAND_NAVY = colors.HexColor("#0F172A")
BRAND_SURFACE = colors.HexColor("#F8FAFC")
BRAND_BORDER = colors.HexColor("#E2E8F0")
BRAND_TEXT = colors.HexColor("#0F172A")
BRAND_MUTED = colors.HexColor("#64748B")
BRAND_SOFT = colors.HexColor("#CBD5E1")
BRAND_ACCENT = colors.HexColor("#2563EB")
BRAND_SUCCESS_BG = colors.HexColor("#DCFCE7")
BRAND_SUCCESS_TEXT = colors.HexColor("#166534")
BRAND_WARNING_BG = colors.HexColor("#FEF3C7")
BRAND_WARNING_TEXT = colors.HexColor("#92400E")
BRAND_DANGER_BG = colors.HexColor("#FEE2E2")
BRAND_DANGER_TEXT = colors.HexColor("#991B1B")


def _format_amount(value):
    return f"{value:,.2f}"


def _format_money(value, currency="KES"):
    return f"{currency} {_format_amount(value)}"


def _safe_text(value):
    return value or "Not provided"


def _status_colors(status):
    palette = {
        "paid": (BRAND_SUCCESS_BG, BRAND_SUCCESS_TEXT),
        "sent": (BRAND_WARNING_BG, BRAND_WARNING_TEXT),
        "draft": (colors.HexColor("#E0E7FF"), colors.HexColor("#3730A3")),
    }
    return palette.get((status or "").lower(), (BRAND_SURFACE, BRAND_TEXT))


def _validate_logo_file(business):
    if not business.logo:
        return False

    try:
        logo_path = business.logo.path
        if not os.path.exists(logo_path):
            logger.warning(
                "Logo file missing for business_id=%s: path=%s",
                business.id,
                logo_path,
            )
            return False
        return True
    except Exception as exc:
        logger.error(
            "Error validating logo for business_id=%s: %s",
            business.id,
            str(exc),
            exc_info=True,
        )
        return False


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Eyebrow",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#BFDBFE"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeroTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeroMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#DBEAFE"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=BRAND_MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=BRAND_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=BRAND_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=BRAND_MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyValue",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=BRAND_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyValueStrong",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=BRAND_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FinePrint",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=12,
            textColor=BRAND_MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Pill",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=BRAND_TEXT,
            alignment=1,
        )
    )
    return styles


def _load_logo(business, log_context):
    if not _validate_logo_file(business):
        return None

    try:
        logo_flowable = Image(business.logo.path)
        logo_flowable.drawHeight = 16 * mm
        logo_flowable.drawWidth = 16 * mm
        logo_flowable.hAlign = "LEFT"
        logger.debug("Logo loaded successfully for %s", log_context)
        return logo_flowable
    except Exception as exc:
        logger.warning("Failed to load logo for %s: %s", log_context, str(exc), exc_info=True)
        return None


def _build_brand_block(title, subtitle, business, styles, log_context):
    logo_flowable = _load_logo(business, log_context)
    title_block = Paragraph(
        f"<font size='8'>{subtitle}</font><br/>{title}",
        styles["HeroTitle"],
    )

    if not logo_flowable:
        return title_block

    table = Table([[logo_flowable, title_block]], colWidths=[18 * mm, 92 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _build_pill(text, background, text_color, width=32 * mm):
    pill = Table([[Paragraph(text.upper(), ParagraphStyle("PillText", fontName="Helvetica-Bold", fontSize=8, textColor=text_color, alignment=1))]], colWidths=[width])
    pill.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BOX", (0, 0), (-1, -1), 0, background),
            ]
        )
    )
    return pill


def _build_header(title, subtitle, meta_lines, badge_text, badge_background, badge_color, business, styles, log_context):
    brand_block = _build_brand_block(title, subtitle, business, styles, log_context)
    badge = _build_pill(badge_text, badge_background, badge_color)
    meta = Paragraph("<br/>".join(meta_lines), styles["HeroMeta"])
    right = Table([[badge], [Spacer(1, 2 * mm)], [meta]], colWidths=[52 * mm])
    right.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    header = Table([[brand_block, right]], colWidths=[112 * mm, 52 * mm])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return header


def _metric_card(label, value, width, styles):
    card = Table(
        [[Paragraph(label, styles["CardLabel"])], [Paragraph(value, styles["CardValue"])]],
        colWidths=[width],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return card


def _build_info_card(title, lines, styles, width):
    rows = [[Paragraph(title.upper(), styles["BodyLabel"])]]
    for line in lines:
        rows.append([Paragraph(line, styles["BodyValue"])])

    card = Table(rows, colWidths=[width])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return card


def _build_totals_card(rows, styles):
    table_rows = []
    for label, value, strong in rows:
        style = styles["BodyValueStrong"] if strong else styles["BodyValue"]
        table_rows.append([Paragraph(label, styles["BodyLabel"]), Paragraph(value, style)])

    card = Table(table_rows, colWidths=[42 * mm, 34 * mm])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, BRAND_SOFT),
                ("BACKGROUND", (0, -1), (-1, -1), colors.white),
            ]
        )
    )
    return card


def _build_items_table(invoice, styles):
    item_rows = [[
        Paragraph("Description", styles["BodyLabel"]),
        Paragraph("Qty", styles["BodyLabel"]),
        Paragraph("Unit Price", styles["BodyLabel"]),
        Paragraph("Line Total", styles["BodyLabel"]),
    ]]

    currency = invoice.currency or "KES"
    for item in invoice.items.all():
        item_rows.append(
            [
                Paragraph(item.description, styles["BodyValue"]),
                Paragraph(str(item.quantity), styles["BodyValue"]),
                Paragraph(_format_money(item.unit_price, currency), styles["BodyValue"]),
                Paragraph(_format_money(item.total, currency), styles["BodyValueStrong"]),
            ]
        )

    table = Table(item_rows, colWidths=[82 * mm, 16 * mm, 32 * mm, 34 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, BRAND_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_SURFACE]),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
            ]
        )
    )
    return table


def _template_palette(template):
    if template == "minimal":
        return {
            "header_bg": colors.white,
            "header_text": BRAND_TEXT,
            "header_meta": BRAND_MUTED,
            "accent": BRAND_TEXT,
            "surface": colors.white,
            "table_header": colors.HexColor("#F1F5F9"),
            "table_header_text": BRAND_TEXT,
        }
    if template == "modern":
        return {
            "header_bg": colors.HexColor("#047857"),
            "header_text": colors.white,
            "header_meta": colors.HexColor("#D1FAE5"),
            "accent": colors.HexColor("#047857"),
            "surface": colors.HexColor("#ECFDF5"),
            "table_header": colors.HexColor("#064E3B"),
            "table_header_text": colors.white,
        }
    return {
        "header_bg": BRAND_NAVY,
        "header_text": colors.white,
        "header_meta": colors.HexColor("#DBEAFE"),
        "accent": BRAND_ACCENT,
        "surface": BRAND_SURFACE,
        "table_header": BRAND_NAVY,
        "table_header_text": colors.white,
    }


def _apply_invoice_template_styles(styles, palette):
    styles["HeroTitle"].textColor = palette["header_text"]
    styles["HeroMeta"].textColor = palette["header_meta"]
    styles["Eyebrow"].textColor = palette["header_meta"]
    styles["SectionTitle"].textColor = palette["accent"]
    return styles


def _build_template_header(title, subtitle, meta_lines, badge_text, badge_background, badge_color, business, styles, log_context, palette):
    header = _build_header(
        title,
        subtitle,
        meta_lines,
        badge_text,
        badge_background,
        badge_color,
        business,
        styles,
        log_context,
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["header_bg"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER if palette["header_bg"] == colors.white else palette["header_bg"]),
            ]
        )
    )
    return header


def _build_template_items_table(invoice, styles, palette):
    table = _build_items_table(invoice, styles)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["table_header"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), palette["table_header_text"]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, BRAND_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["surface"]]),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
            ]
        )
    )
    return table


def generate_invoice_pdf(invoice, template=None):
    styles = _build_styles()
    selected_template = template or getattr(invoice, "template", "classic") or "classic"
    palette = _template_palette(selected_template)
    styles = _apply_invoice_template_styles(styles, palette)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=PAGE_MARGIN,
        leftMargin=PAGE_MARGIN,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    badge_bg, badge_text = _status_colors(invoice.status)
    currency = invoice.currency or "KES"
    amount_due = _format_money(invoice.balance_due, currency)

    header = _build_template_header(
        title=invoice.business.display_name or invoice.business.name,
        subtitle=f"Invoice {invoice.invoice_number}",
        meta_lines=[
            f"Issued: {invoice.issue_date}",
            f"Due: {invoice.due_date}",
            f"Currency: {currency}",
        ],
        badge_text=invoice.status,
        badge_background=badge_bg,
        badge_color=badge_text,
        business=invoice.business,
        styles=styles,
        log_context=f"business_id={invoice.business.id}, invoice_number={invoice.invoice_number}",
        palette=palette,
    )

    summary_cards = Table(
        [[
            _metric_card("Amount Due", amount_due, 52 * mm, styles),
            _metric_card("Amount Paid", _format_money(invoice.amount_paid, currency), 52 * mm, styles),
            _metric_card("Balance", amount_due, 52 * mm, styles),
        ]],
        colWidths=[54 * mm, 54 * mm, 54 * mm],
    )
    summary_cards.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    parties = Table(
        [[
            _build_info_card(
                "Bill From",
                [
                    f"<b>{invoice.business.display_name or invoice.business.name}</b>",
                    _safe_text(invoice.business.email),
                    _safe_text(invoice.business.phone),
                    _safe_text(invoice.business.address),
                ],
                styles,
                80 * mm,
            ),
            _build_info_card(
                "Bill To",
                [
                    f"<b>{invoice.client_name}</b>",
                    _safe_text(invoice.client_email),
                ],
                styles,
                80 * mm,
            ),
        ]],
        colWidths=[82 * mm, 82 * mm],
    )
    parties.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    totals = _build_totals_card(
        [
            ("Subtotal", _format_money(invoice.subtotal, currency), False),
            (f"VAT ({invoice.business.tax_rate}%)", _format_money(invoice.tax_amount, currency), False),
            ("Total", _format_money(invoice.total_amount, currency), True),
        ],
        styles,
    )

    notes_rows = [
        [Paragraph("Payment Summary", styles["SectionTitle"])],
        [Paragraph(
            (
                f"This invoice is currently <b>{invoice.status}</b>. "
                f"The current balance due is <b>{amount_due}</b>."
            ),
            styles["BodyValue"],
        )]
    ]
    if invoice.tax_invoice_number:
        notes_rows.append([
            Paragraph(f"KRA eTIMS Tax Invoice Number: <b>{invoice.tax_invoice_number}</b>", styles["BodyValue"])
        ])

    payment_summary = Table(notes_rows, colWidths=[CONTENT_WIDTH])
    payment_summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 7 * mm),
        summary_cards,
        Spacer(1, 7 * mm),
        parties,
        Spacer(1, 7 * mm),
        Paragraph("Invoice Items", styles["SectionTitle"]),
        Spacer(1, 2.5 * mm),
        _build_template_items_table(invoice, styles, palette),
        Spacer(1, 7 * mm),
        Table([["", totals]], colWidths=[86 * mm, 78 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])),
        Spacer(1, 7 * mm),
        payment_summary,
        Spacer(1, 6 * mm),
        Paragraph(
            "Thank you for your business. Please use the invoice number as your payment reference whenever possible.",
            styles["FinePrint"],
        ),
    ]

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_receipt_pdf(receipt):
    styles = _build_styles()
    invoice = receipt.invoice
    currency = receipt.currency or invoice.currency or "KES"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=PAGE_MARGIN,
        leftMargin=PAGE_MARGIN,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    payment_state = "Payment Received"
    balance = invoice.balance_due
    receipt_message = (
        "This payment settles the invoice in full."
        if balance == 0
        else f"This payment was recorded successfully. Remaining balance: {_format_money(balance, currency)}."
    )

    header = _build_header(
        title=invoice.business.display_name or invoice.business.name,
        subtitle=f"Receipt {receipt.receipt_number}",
        meta_lines=[
            f"Payment Date: {receipt.payment_date}",
            f"Invoice: {invoice.invoice_number}",
            f"Currency: {currency}",
        ],
        badge_text=payment_state,
        badge_background=BRAND_SUCCESS_BG,
        badge_color=BRAND_SUCCESS_TEXT,
        business=invoice.business,
        styles=styles,
        log_context=f"receipt_number={receipt.receipt_number}, invoice_number={invoice.invoice_number}",
    )

    summary_cards = Table(
        [[
            _metric_card("Amount Paid", _format_money(receipt.amount_paid, currency), 52 * mm, styles),
            _metric_card("Invoice Total", _format_money(invoice.total_amount, currency), 52 * mm, styles),
            _metric_card("Balance After Payment", _format_money(balance, currency), 52 * mm, styles),
        ]],
        colWidths=[54 * mm, 54 * mm, 54 * mm],
    )
    summary_cards.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    payment_details = Table(
        [
            [
                _build_info_card(
                    "Received From",
                    [
                        f"<b>{invoice.client_name}</b>",
                        _safe_text(invoice.client_email),
                    ],
                    styles,
                    80 * mm,
                ),
                _build_info_card(
                    "Receipt Details",
                    [
                        f"<b>{receipt.receipt_number}</b>",
                        f"Method: {receipt.get_payment_method_display()}",
                        f"Reference: {_safe_text(receipt.reference)}",
                        f"Invoice: {invoice.invoice_number}",
                    ],
                    styles,
                    80 * mm,
                ),
            ]
        ],
        colWidths=[82 * mm, 82 * mm],
    )
    payment_details.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    allocation = _build_totals_card(
        [
            ("Payment Date", str(receipt.payment_date), False),
            ("Amount Applied", _format_money(receipt.amount_paid, currency), False),
            ("Balance Remaining", _format_money(balance, currency), True),
        ],
        styles,
    )

    notes_rows = [
        [Paragraph("Payment Note", styles["SectionTitle"])],
        [Paragraph(receipt_message, styles["BodyValue"])],
    ]
    if receipt.notes:
        notes_rows.append([Paragraph(f"Notes: {_safe_text(receipt.notes)}", styles["BodyValue"])])

    note_card = Table(notes_rows, colWidths=[CONTENT_WIDTH])
    note_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BRAND_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 7 * mm),
        summary_cards,
        Spacer(1, 7 * mm),
        payment_details,
        Spacer(1, 7 * mm),
        Table([["", allocation]], colWidths=[86 * mm, 78 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])),
        Spacer(1, 7 * mm),
        note_card,
        Spacer(1, 6 * mm),
        Paragraph(
            "Keep this receipt for your records. It confirms the payment captured in SmartInvoice.",
            styles["FinePrint"],
        ),
    ]

    doc.build(story)
    buffer.seek(0)
    return buffer
