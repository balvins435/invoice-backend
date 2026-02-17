from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _format_amount(value):
    return f"{value:,.2f}"


def _build_business_header(invoice, styles):
    header_title = Paragraph(
        f"{invoice.business.name}<br/><font size='11'>Invoice {invoice.invoice_number}</font>",
        styles["BusinessName"],
    )

    logo_flowable = None
    if invoice.business.logo:
        try:
            logo_flowable = Image(invoice.business.logo.path)
            logo_flowable.drawHeight = 14 * mm
            logo_flowable.drawWidth = 14 * mm
            logo_flowable.hAlign = "LEFT"
        except Exception:
            logo_flowable = None

    left_content = [[header_title]]
    left_widths = [112 * mm]
    if logo_flowable:
        left_content = [[logo_flowable, header_title]]
        left_widths = [16 * mm, 96 * mm]

    left_cell = Table(left_content, colWidths=left_widths)
    left_cell.setStyle(
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

    return left_cell


def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="MetaLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.HexColor("#6B7280"),
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetaValue",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#111827"),
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#111827"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BusinessName",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=colors.white,
            leading=26,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeaderSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#DBEAFE"),
            leading=14,
        )
    )

    header = Table(
        [[
            _build_business_header(invoice, styles),
            Paragraph(
                (
                    f"<para align='right'><font name='Helvetica-Bold' size='11' color='#DBEAFE'>"
                    f"Status: {invoice.status.title()}</font><br/>"
                    f"<font color='#BFDBFE'>Issued: {invoice.issue_date}</font><br/>"
                    f"<font color='#BFDBFE'>Due: {invoice.due_date}</font></para>"
                ),
                styles["HeaderSubtitle"],
            ),
        ]],
        colWidths=[112 * mm, 52 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )

    details = Table(
        [
            [
                Paragraph("BILL FROM", styles["MetaLabel"]),
                Paragraph("BILL TO", styles["MetaLabel"]),
            ],
            [
                Paragraph(
                    (
                        f"<font name='Helvetica-Bold'>{invoice.business.name}</font><br/>"
                        f"{invoice.business.email}<br/>"
                        f"{invoice.business.phone}<br/>"
                        f"{invoice.business.address}"
                    ),
                    styles["MetaValue"],
                ),
                Paragraph(
                    (
                        f"<font name='Helvetica-Bold'>{invoice.client_name}</font><br/>"
                        f"{invoice.client_email}"
                    ),
                    styles["MetaValue"],
                ),
            ],
        ],
        colWidths=[82 * mm, 82 * mm],
    )
    details.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
            ]
        )
    )

    item_rows = [["Description", "Qty", "Unit Price", "Amount"]]
    for item in invoice.items.all():
        item_rows.append(
            [
                item.description,
                str(item.quantity),
                f"KES {_format_amount(item.unit_price)}",
                f"KES {_format_amount(item.total)}",
            ]
        )

    items_table = Table(item_rows, colWidths=[86 * mm, 18 * mm, 30 * mm, 30 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )

    totals_table = Table(
        [
            ["Subtotal", f"KES {_format_amount(invoice.subtotal)}"],
            [f"VAT ({invoice.business.tax_rate}%)", f"KES {_format_amount(invoice.tax_amount)}"],
            ["Total", f"KES {_format_amount(invoice.total_amount)}"],
        ],
        colWidths=[38 * mm, 36 * mm],
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEABOVE", (0, -1), (-1, -1), 1.1, colors.HexColor("#334155")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 8 * mm),
        details,
        Spacer(1, 8 * mm),
        Paragraph("Invoice Items", styles["SectionTitle"]),
        Spacer(1, 3 * mm),
        items_table,
        Spacer(1, 8 * mm),
        Table([["", totals_table]], colWidths=[90 * mm, 74 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])),
        Spacer(1, 8 * mm),
        Paragraph(
            "Thank you for your business. Please pay before the due date to avoid interruptions.",
            ParagraphStyle(
                "FooterNote",
                parent=styles["Normal"],
                textColor=colors.HexColor("#475569"),
                fontSize=9,
                leading=12,
            ),
        ),
    ]

    doc.build(story)

    buffer.seek(0)
    return buffer
