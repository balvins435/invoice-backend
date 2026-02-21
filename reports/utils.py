from io import BytesIO
from calendar import month_name
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import monthly_report, monthly_reports_for_year, tax_summary


def _format_amount(value):
    return f"KES {value:,.2f}"


def _build_business_header(business, styles):
    logo_flowable = None
    if business.logo:
        try:
            logo_flowable = Image(business.logo.path)
            logo_flowable.drawHeight = 12 * mm
            logo_flowable.drawWidth = 12 * mm
            logo_flowable.hAlign = "LEFT"
        except Exception:
            logo_flowable = None

    address_lines = [
        business.address.replace("\n", "<br/>"),
        business.email,
        business.phone,
    ]
    address_html = "<br/>".join([line for line in address_lines if line])
    info = Paragraph(address_html, styles["HeaderInfo"])

    if logo_flowable:
        header_table = Table([[logo_flowable, info]], colWidths=[14 * mm, 52 * mm])
        header_table.setStyle(
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
        return header_table

    return info


def _kpi_card(title, value, accent, soft_bg, styles):
    label = Paragraph(f"<font color='{accent}' size='8'><b>{title}</b></font>", styles["KpiLabel"])
    amount = Paragraph(f"<font color='#0F172A' size='12'><b>{value}</b></font>", styles["KpiValue"])
    card = Table([[label], [amount]], colWidths=[70 * mm])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(soft_bg)),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(accent)),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return card


def generate_report_pdf(business, year, month=None):
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
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=colors.HexColor("#0F172A"),
            leading=24,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeaderTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=colors.white,
            leading=24,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#94A3B8"),
            leading=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeaderInfo",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#E2E8F0"),
            leading=11,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#0F172A"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetaText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#64748B"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="KpiLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KpiValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
        )
    )

    period_label = f"{month_name[int(month)]} {year}" if month else f"{year} Summary"

    header = Table(
        [[
            Paragraph("Financial Summary Report", styles["HeaderTitle"]),
            _build_business_header(business, styles),
        ]],
        colWidths=[102 * mm, 68 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 6 * mm),
        Paragraph(f"Period: {period_label}", styles["MetaText"]),
        Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["MetaText"]),
        Spacer(1, 6 * mm),
    ]

    if month:
        report = monthly_report(business=business, month=int(month), year=year)
        totals = report
    else:
        reports = monthly_reports_for_year(business=business, year=year)
        totals = {
            "total_income": sum(r["total_income"] for r in reports),
            "total_expenses": sum(r["total_expenses"] for r in reports),
            "tax_owed": sum(r["tax_owed"] for r in reports),
            "deductible_expenses": sum(r["deductible_expenses"] for r in reports),
            "net_profit": sum(r["net_profit"] for r in reports),
            "invoice_count": sum(r["invoice_count"] for r in reports),
            "expense_count": sum(r["expense_count"] for r in reports),
        }

    story.append(Paragraph("Summary", styles["SectionTitle"]))
    story.append(Spacer(1, 2 * mm))
    income_card = _kpi_card("Total Income", _format_amount(totals["total_income"]), "#10B981", "#ECFDF5", styles)
    expense_card = _kpi_card("Total Expenses", _format_amount(totals["total_expenses"]), "#EF4444", "#FEF2F2", styles)
    profit_card = _kpi_card("Net Profit", _format_amount(totals["net_profit"]), "#2563EB", "#EFF6FF", styles)
    tax_card = _kpi_card("Tax Owed", _format_amount(totals["tax_owed"]), "#F59E0B", "#FFFBEB", styles)

    kpi_grid = Table(
        [[income_card, expense_card], [profit_card, tax_card]],
        colWidths=[80 * mm, 80 * mm],
        rowHeights=[24 * mm, 24 * mm],
    )
    kpi_grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("INNERGRID", (0, 0), (-1, -1), 4, colors.white),
            ]
        )
    )
    story.append(kpi_grid)
    story.append(Spacer(1, 7 * mm))

    tax = tax_summary(business=business, year=year, month=int(month) if month else None)
    tax_rows = [
        ["Tax Collected", _format_amount(tax["total_tax_collected"])],
        ["Tax Deductible", _format_amount(tax["total_tax_deductible"])],
        ["Net Tax Liability", _format_amount(tax["net_tax_liability"])],
    ]
    story.append(Paragraph("Tax Summary", styles["SectionTitle"]))
    story.append(Spacer(1, 2 * mm))
    tax_table = Table(tax_rows, colWidths=[58 * mm, 50 * mm])
    tax_table.setStyle(
        TableStyle(
            [
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    story.append(tax_table)

    if not month:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("Monthly Breakdown", styles["SectionTitle"]))
        story.append(Spacer(1, 2 * mm))
        monthly_rows = [["Month", "Income", "Expenses", "Net Profit", "Tax Owed"]]
        for report in reports:
            monthly_rows.append(
                [
                    report["month"],
                    _format_amount(report["total_income"]),
                    _format_amount(report["total_expenses"]),
                    _format_amount(report["net_profit"]),
                    _format_amount(report["tax_owed"]),
                ]
            )
        monthly_table = Table(monthly_rows, colWidths=[32 * mm, 32 * mm, 32 * mm, 32 * mm, 32 * mm])
        monthly_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ]
            )
        )
        story.append(monthly_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
