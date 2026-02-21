from io import BytesIO
from calendar import month_name
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import monthly_report, monthly_reports_for_year, tax_summary


def _format_amount(value):
    return f"KES {value:,.2f}"


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

    period_label = f"{month_name[int(month)]} {year}" if month else f"{year} Summary"

    story = [
        Paragraph("Financial Report", styles["ReportTitle"]),
        Paragraph(business.name, styles["MetaText"]),
        Paragraph(f"Period: {period_label}", styles["MetaText"]),
        Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["MetaText"]),
        Spacer(1, 8 * mm),
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

    summary_rows = [
        ["Total Income", _format_amount(totals["total_income"])],
        ["Total Expenses", _format_amount(totals["total_expenses"])],
        ["Net Profit", _format_amount(totals["net_profit"])],
        ["Tax Owed", _format_amount(totals["tax_owed"])],
        ["Deductible Expenses", _format_amount(totals["deductible_expenses"])],
        ["Invoices", str(totals["invoice_count"])],
        ["Expenses", str(totals["expense_count"])],
    ]

    story.append(Paragraph("Summary", styles["SectionTitle"]))
    story.append(Spacer(1, 2 * mm))
    summary_table = Table(summary_rows, colWidths=[58 * mm, 50 * mm])
    summary_table.setStyle(
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
    story.append(summary_table)
    story.append(Spacer(1, 8 * mm))

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
