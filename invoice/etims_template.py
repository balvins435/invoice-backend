"""Kenya Revenue Authority eTIMS tax invoice layout.

This renders the "Tax Invoice" form produced by KRA's electronic Tax Invoice
Management System: a supplier/customer block, the line item grid, the SCU
information panel, the verification QR code and the tax summary grid.

The builder has no Django imports on purpose. ``invoice.utils`` resolves model
data into a plain ``context`` dict and calls :func:`build_etims_pdf`, which
keeps the layout testable and reusable outside a Django process.
"""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

try:  # Only required to draw the eTIMS verification QR code.
    import qrcode
except ImportError:  # pragma: no cover - the panel degrades to a placeholder
    qrcode = None


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 10 * mm
CONTENT_LEFT = MARGIN
CONTENT_RIGHT = PAGE_WIDTH - MARGIN
CONTENT_WIDTH = CONTENT_RIGHT - CONTENT_LEFT

INK = colors.HexColor("#111111")
RULE = colors.HexColor("#111111")
HEAD_FILL = colors.HexColor("#EAEAEA")
PLACEHOLDER = colors.HexColor("#B4B4B4")

MONO = "Courier"
MONO_BOLD = "Courier-Bold"
BODY_SIZE = 7.5
HEAD_SIZE = 8
TITLE_SIZE = 17
LINE = 9.6
CELL_PAD = 3
ROW_PAD = 3.4

# Proportions taken from the eTIMS form so the grid lines up with the original.
ITEM_COLUMNS = (0.15, 0.19, 0.15, 0.06, 0.15, 0.15, 0.15)
ITEM_HEADINGS = (
    "Item Code",
    "Item Description",
    "Qty x Unit Price",
    "Rate",
    "Amt excl. Tax",
    "Tax Amt",
    "Amt incl. Tax",
)
SUMMARY_COLUMNS = (0.16, 0.28, 0.28, 0.28)
SUMMARY_HEADINGS = ("Tax Rate", "Taxable Amt", "Tax Amt", "Total Amt")
SUMMARY_ROWS = ("16%", "8%", "0%", "Ex.")

SUMMARY_WIDTH = CONTENT_WIDTH * 0.52
QR_COLUMN_WIDTH = CONTENT_WIDTH * 0.13
SCU_COLUMN_WIDTH = CONTENT_WIDTH - SUMMARY_WIDTH - QR_COLUMN_WIDTH

DASH_RULE = "-" * 36


def _money(value):
    """Format a number the way the eTIMS form does: 1,234,567.00."""
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        amount = Decimal("0.00")
    return f"{amount:,.2f}"


def _rate_label(value):
    try:
        rate = Decimal(str(value or 0)).normalize()
    except Exception:
        return "0%"
    text = format(rate, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%"


def _display(value, fallback="-"):
    text = str(value or "").strip()
    return text or fallback


def _wrap(text, font, size, max_width):
    """Greedy character wrap; descriptions on the eTIMS form are hard wrapped."""
    words = str(text or "").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit(text, font, size, max_width):
    """Truncate with an ellipsis so a cell can never overflow its column."""
    text = str(text or "")
    if stringWidth(text, font, size) <= max_width:
        return text
    ellipsis = "..."
    trimmed = text
    while trimmed and stringWidth(trimmed + ellipsis, font, size) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def _cell_lines(text, font, size, max_width, max_lines):
    lines = _wrap(text, font, size, max_width)
    if len(lines) <= max_lines:
        return lines
    kept = lines[: max_lines - 1] + [lines[max_lines - 1]]
    return kept


def _draw_lines(pdf, x, y, lines, font, size, leading):
    pdf.setFont(font, size)
    cursor = y
    for line in lines:
        pdf.drawString(x, cursor, line)
        cursor -= leading
    return cursor


class _EtimsDocument:
    """Draws one eTIMS tax invoice, paginating the item grid when needed."""

    def __init__(self, buffer, context):
        self.pdf = pdfcanvas.Canvas(buffer, pagesize=A4)
        self.pdf.setTitle(f"Tax invoice {context.get('invoice_number', '')}".strip())
        author = str(context.get("business_name") or "").strip()
        if author:
            self.pdf.setAuthor(author)
        self.context = context
        self.currency = context.get("currency_symbol") or "KSh"
        self.tax_rate = Decimal(str(context.get("tax_rate") or 0))
        self.items = list(context.get("items") or [])

    # -- page furniture -------------------------------------------------

    def _rule(self, y):
        self.pdf.setStrokeColor(RULE)
        self.pdf.setLineWidth(0.6)
        self.pdf.line(CONTENT_LEFT, y, CONTENT_RIGHT, y)

    def _draw_masthead(self, top):
        """Business identity on the left, form caption on the right."""
        pdf = self.pdf
        cursor = top
        logo = self.context.get("logo")
        drawn_logo = False
        if logo:
            try:
                image = ImageReader(BytesIO(logo))
                width, height = image.getSize()
                scale = min((46 * mm) / width, (14 * mm) / height)
                pdf.drawImage(
                    image,
                    CONTENT_LEFT,
                    cursor - (height * scale),
                    width=width * scale,
                    height=height * scale,
                    mask="auto",
                )
                drawn_logo = True
            except Exception:
                drawn_logo = False
        if not drawn_logo:
            pdf.setFillColor(INK)
            pdf.setFont(MONO_BOLD, 15)
            pdf.drawString(CONTENT_LEFT, cursor - 12, _fit(self.context.get("business_name", ""), MONO_BOLD, 15, CONTENT_WIDTH * 0.55))

        pdf.setFillColor(INK)
        pdf.setFont(MONO, 10)
        pdf.drawRightString(CONTENT_RIGHT, cursor - 10, "TAX INVOICE")
        pdf.setFont(MONO, 7)
        pdf.drawRightString(CONTENT_RIGHT, cursor - 21, "eTIMS")
        return cursor - (20 * mm)

    def _draw_party_box(self, x, top, width, title, pin, name):
        """One bordered INVOICE FROM / INVOICE TO box."""
        pdf = self.pdf
        body_font = MONO
        head_font = MONO_BOLD
        inner = width - (CELL_PAD * 2)
        name_lines = _wrap(f"NAME: {_display(name)}", body_font, BODY_SIZE, inner)
        height = 2 * LINE + (len(name_lines) * LINE) + (CELL_PAD * 2) + 6

        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(0.7)
        pdf.rect(x, top - height, width, height, stroke=1, fill=0)

        cursor = top - CELL_PAD - 5
        pdf.setFillColor(INK)
        _draw_lines(pdf, x + CELL_PAD, cursor, [title], head_font, HEAD_SIZE, LINE)
        cursor -= LINE + 1.5
        _draw_lines(pdf, x + CELL_PAD, cursor, [f"PIN: {_display(pin)}"], body_font, BODY_SIZE, LINE)
        cursor -= LINE
        _draw_lines(pdf, x + CELL_PAD, cursor, name_lines, body_font, BODY_SIZE, LINE)
        return height

    def _draw_invoice_box(self, x, top, width):
        pdf = self.pdf
        reference = _display(
            self.context.get("tax_invoice_number") or self.context.get("invoice_number"),
        )
        date_line = f"Date : {_display(self.context.get('issued_at_text'), '')}"
        inner = width - (CELL_PAD * 2)
        ref_lines = _wrap(f"INVOICE NO: {reference}", MONO, BODY_SIZE, inner)
        height = LINE + (len(ref_lines) * LINE) + (CELL_PAD * 2) + 5

        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(0.7)
        pdf.rect(x, top - height, width, height, stroke=1, fill=0)

        cursor = top - CELL_PAD - 5
        pdf.setFillColor(INK)
        _draw_lines(pdf, x + CELL_PAD, cursor, ref_lines, MONO_BOLD, BODY_SIZE, LINE)
        cursor -= LINE * len(ref_lines) * 0.0 + LINE
        _draw_lines(pdf, x + CELL_PAD, cursor, [_fit(date_line, MONO, BODY_SIZE, inner)], MONO, BODY_SIZE, LINE)
        return height

    def _draw_header_blocks(self, top):
        gap = 6 * mm
        usable = CONTENT_WIDTH - (gap * 2)
        first = usable * 0.32
        second = usable * 0.34
        third = usable - first - second

        x = CONTENT_LEFT
        h1 = self._draw_party_box(
            x, top, first,
            "INVOICE FROM",
            self.context.get("business_pin"),
            self.context.get("business_name"),
        )
        x += first + gap
        h2 = self._draw_party_box(
            x, top, second,
            "INVOICE TO",
            self.context.get("client_pin"),
            self.context.get("client_name"),
        )
        x += second + gap
        h3 = self._draw_invoice_box(x, top, third)
        return top - max(h1, h2, h3)

    # -- item grid ------------------------------------------------------

    def _item_row(self, item):
        code = _display(item.get("code"), "")
        description = str(item.get("description") or "")
        quantity = str(item.get("quantity") or 0)
        quantity_decimal = Decimal(str(item.get("quantity") or 0))
        unit_price = Decimal(str(item.get("unit_price") or 0))
        excl = Decimal(str(item.get("total") or 0))
        if not excl:
            excl = quantity_decimal * unit_price
        tax = (excl * self.tax_rate / Decimal("100")) if self.tax_rate else Decimal("0.00")
        incl = excl + tax
        incl_unit = unit_price * (Decimal("1") + self.tax_rate / Decimal("100"))

        widths = [CONTENT_WIDTH * fraction for fraction in ITEM_COLUMNS]
        inner = [w - (CELL_PAD * 2) for w in widths]
        desc_lines = _cell_lines(description, MONO, BODY_SIZE, inner[1], 5)
        height = max(len(desc_lines) * LINE + (ROW_PAD * 2), 18)

        cells = [
            _wrap(code, MONO, BODY_SIZE, inner[0])[:1],
            desc_lines,
            [f"{quantity} x {_money(incl_unit)}"],
            [_rate_label(self.tax_rate)],
            [_money(excl)],
            [_money(tax)],
            [_money(incl)],
        ]
        return {"cells": cells, "height": height, "widths": widths}

    def _draw_grid_header(self, top):
        widths = [CONTENT_WIDTH * fraction for fraction in ITEM_COLUMNS]
        height = LINE + (CELL_PAD * 2) + 4
        pdf = self.pdf
        pdf.setFillColor(HEAD_FILL)
        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(0.7)
        pdf.rect(CONTENT_LEFT, top - height, CONTENT_WIDTH, height, stroke=1, fill=1)

        pdf.setFillColor(INK)
        x = CONTENT_LEFT
        for index, heading in enumerate(ITEM_HEADINGS):
            inner = widths[index] - (CELL_PAD * 2)
            pdf.setFont(MONO_BOLD, HEAD_SIZE)
            pdf.drawString(x + CELL_PAD, top - height + CELL_PAD + 2, _fit(heading, MONO_BOLD, HEAD_SIZE, inner))
            x += widths[index]
        x = CONTENT_LEFT
        for index in range(len(widths) - 1):
            x += widths[index]
            pdf.line(x, top - height, x, top)
        return top - height

    def _draw_item_row(self, row, top):
        """Draw one row of cells. Column rules come from ``_draw_grid_frame``."""
        pdf = self.pdf
        bottom = top - row["height"]
        x = CONTENT_LEFT
        pdf.setFillColor(INK)
        pdf.setFont(MONO, BODY_SIZE)
        for index, lines in enumerate(row["cells"]):
            cursor = top - ROW_PAD - BODY_SIZE
            for line in lines:
                pdf.drawString(x + CELL_PAD, cursor, line)
                cursor -= LINE
            x += row["widths"][index]
        return bottom

    def _draw_grid_frame(self, top, bottom):
        """Vertical column rules spanning the whole grid body."""
        widths = [CONTENT_WIDTH * fraction for fraction in ITEM_COLUMNS]
        pdf = self.pdf
        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(0.5)
        x = CONTENT_LEFT
        pdf.line(x, bottom, x, top)
        for index in range(len(widths) - 1):
            x += widths[index]
            pdf.line(x, bottom, x, top)
        pdf.line(CONTENT_RIGHT, bottom, CONTENT_RIGHT, top)

    # -- bottom block ---------------------------------------------------

    def _draw_scu_panel(self, top, width):
        pdf = self.pdf
        context = self.context
        lines = [
            ("SCU INFORMATION", MONO_BOLD, HEAD_SIZE),
            (DASH_RULE, MONO, BODY_SIZE),
            (f"Date : {_display(context.get('issued_at_text'), '')}", MONO, BODY_SIZE),
            (f"SCU ID : {_display(context.get('scu_id'))}", MONO, BODY_SIZE),
            ("", MONO, BODY_SIZE),
            ("CU INVOICE NO. :", MONO, BODY_SIZE),
            (_display(context.get("tax_invoice_number") or context.get("invoice_number")), MONO, BODY_SIZE),
            ("", MONO, BODY_SIZE),
        ]
        internal = _display(context.get("internal_data"))
        signature = _display(context.get("receipt_signature"))
        lines.append((f"Internal Data : {internal[:17]}", MONO, BODY_SIZE))
        if len(internal) > 17:
            lines.append((internal[17:], MONO, BODY_SIZE))
        lines.append((f"Receipt Signature : {signature[:18]}", MONO, BODY_SIZE))
        if len(signature) > 18:
            lines.append((signature[18:], MONO, BODY_SIZE))
        lines.append((DASH_RULE, MONO, BODY_SIZE))
        lines.append(("Powered by eTIMS", MONO, BODY_SIZE))

        cursor = top
        pdf.setFillColor(INK)
        for text, font, size in lines:
            if text:
                pdf.setFont(font, size)
                pdf.drawString(CONTENT_LEFT, cursor, _fit(text, font, size, width))
            cursor -= LINE
        return cursor

    def _draw_qr(self, top, x, width):
        pdf = self.pdf
        size = min(width, 26 * mm)
        payload = str(self.context.get("qr_payload") or "").strip()
        left = x + max(0, (width - size) / 2)
        if payload and qrcode is not None:
            try:
                image = qrcode.make(payload)
                stream = BytesIO()
                image.save(stream, format="PNG")
                stream.seek(0)
                pdf.drawImage(ImageReader(stream), left, top - size, width=size, height=size, mask="auto")
                return
            except Exception:
                pass
        # No verifiable payload yet: reserve the space so the layout stays stable.
        pdf.setStrokeColor(PLACEHOLDER)
        pdf.setLineWidth(0.6)
        pdf.rect(left, top - size, size, size, stroke=1, fill=0)
        pdf.setFillColor(PLACEHOLDER)
        pdf.setFont(MONO, 6.5)
        pdf.drawCentredString(left + size / 2, top - (size / 2), "QR pending")

    def _summary_rows(self):
        rate_label = _rate_label(self.tax_rate)
        subtotal = Decimal(str(self.context.get("subtotal") or 0))
        tax = Decimal(str(self.context.get("tax_amount") or 0))
        total = Decimal(str(self.context.get("total_amount") or 0))
        rows = []
        for label in SUMMARY_ROWS:
            if label == rate_label:
                rows.append((label, _money(subtotal), _money(tax), _money(total)))
            else:
                rows.append((label, _money(0), _money(0), _money(0)))
        rows.append(("Totals", _money(subtotal), _money(tax), _money(total)))
        return rows

    def _draw_summary(self, top, x, width):
        pdf = self.pdf
        rows = self._summary_rows()
        widths = [width * fraction for fraction in SUMMARY_COLUMNS]
        head_height = LINE + (CELL_PAD * 2) + 3
        row_height = LINE + (CELL_PAD * 2) + 1

        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(0.7)
        pdf.setFillColor(HEAD_FILL)
        pdf.rect(x, top - head_height, width, head_height, stroke=1, fill=1)
        pdf.setFillColor(INK)
        cursor = x
        for index, heading in enumerate(SUMMARY_HEADINGS):
            pdf.setFont(MONO_BOLD, HEAD_SIZE)
            pdf.drawString(cursor + CELL_PAD, top - head_height + CELL_PAD + 1, _fit(heading, MONO_BOLD, HEAD_SIZE, widths[index] - (CELL_PAD * 2)))
            cursor += widths[index]

        y = top - head_height
        pdf.setFont(MONO_BOLD, BODY_SIZE)
        pdf.drawString(x + CELL_PAD, y + CELL_PAD + 9, "TAX SUMMARY")
        y -= (LINE + CELL_PAD)
        pdf.setFillColor(INK)

        for row_index, row in enumerate(rows):
            bottom = y - row_height
            last = row_index == len(rows) - 1
            for column, value in enumerate(row):
                cell_left = x + sum(widths[:column])
                pdf.setStrokeColor(RULE)
                pdf.setLineWidth(0.5)
                pdf.rect(cell_left, bottom, widths[column], row_height, stroke=1, fill=0)
                pdf.setFillColor(INK)
                pdf.setFont(MONO_BOLD if (column == 0 or last) else MONO, BODY_SIZE)
                text = value if column == 0 else f"{self.currency} {value}"
                pdf.drawString(cell_left + CELL_PAD, bottom + CELL_PAD + 2, _fit(text, MONO, BODY_SIZE, widths[column] - (CELL_PAD * 2)))
            y = bottom
        return y

    def _draw_bottom_blocks(self, top):
        summary_bottom = self._draw_summary(top, CONTENT_RIGHT - SUMMARY_WIDTH, SUMMARY_WIDTH)
        self._draw_qr(top, CONTENT_LEFT + SCU_COLUMN_WIDTH, QR_COLUMN_WIDTH)
        scu_bottom = self._draw_scu_panel(top, SCU_COLUMN_WIDTH - CELL_PAD)
        return min(summary_bottom, scu_bottom)

    def _draw_footer(self):
        pdf = self.pdf
        pdf.setFillColor(INK)
        pdf.setFont(MONO, 6.5)
        reference = _display(self.context.get("tax_invoice_number") or self.context.get("invoice_number"))
        pdf.drawString(CONTENT_LEFT, MARGIN - 10, f"{self.currency} tax invoice - {reference}")
        pdf.drawRightString(CONTENT_RIGHT, MARGIN - 10, "Page %d" % pdf.getPageNumber())

    # -- pagination -----------------------------------------------------

    def _bottom_block_height(self):
        # SCU panel: 13 fixed lines plus wrapped internal data / signature.
        return LINE * 16

    def build(self):
        top = PAGE_HEIGHT - MARGIN
        pdf = self.pdf

        if self.items:
            all_rows = [self._item_row(item) for item in self.items]
        else:
            all_rows = []

        cursor = self._draw_masthead(top)
        cursor -= 6 * mm
        cursor = self._draw_header_blocks(cursor) - 6 * mm
        header_bottom = cursor

        index = 0
        first_page = True
        while True:
            if not first_page:
                pdf.showPage()
                cursor = PAGE_HEIGHT - MARGIN
                pdf.setFillColor(INK)
                pdf.setFont(MONO_BOLD, 10)
                pdf.drawString(CONTENT_LEFT, cursor - 10, "TAX INVOICE (continued)")
                cursor -= 18
                header_bottom = cursor
                pdf.setFont(MONO, 7)
                reference = _display(self.context.get("tax_invoice_number") or self.context.get("invoice_number"))
                pdf.drawRightString(CONTENT_RIGHT, PAGE_HEIGHT - MARGIN - 10, reference)

            grid_top = self._draw_grid_header(header_bottom)
            footer_limit = MARGIN + 22
            bottom_limit = footer_limit + self._bottom_block_height() + (6 * mm)

            remaining = all_rows[index:]
            placed = []
            used = 0.0
            available_full = grid_top - footer_limit
            available_last = grid_top - bottom_limit

            # If everything left fits above the bottom block, this is the final page.
            total_remaining = sum(row["height"] for row in remaining)
            final_page = total_remaining <= available_last
            available = available_last if final_page else available_full

            while index < len(all_rows):
                row = all_rows[index]
                if used + row["height"] > available:
                    break
                placed.append(row)
                used += row["height"]
                index += 1

            if not placed and index < len(all_rows):
                # A single row taller than the page: force it through.
                placed.append(all_rows[index])
                used += all_rows[index]["height"]
                index += 1

            bottom = grid_top
            for row in placed:
                bottom = self._draw_item_row(row, bottom)
            # On the last page the grid runs all the way down to the bottom
            # block, exactly like the eTIMS form, so the page is never left
            # half empty. Continuation pages close right under the last row.
            grid_bottom = bottom_limit if final_page else bottom
            self._draw_grid_frame(grid_top, grid_bottom)
            pdf.setStrokeColor(RULE)
            pdf.setLineWidth(0.7)
            pdf.line(CONTENT_LEFT, grid_bottom, CONTENT_RIGHT, grid_bottom)

            if index >= len(all_rows):
                self._draw_bottom_blocks(grid_bottom - 6 * mm)
                self._draw_footer()
                break

            first_page = False

        pdf.save()


def build_etims_pdf(context):
    """Return a ``BytesIO`` holding the rendered eTIMS tax invoice."""
    buffer = BytesIO()
    _EtimsDocument(buffer, context or {}).build()
    buffer.seek(0)
    return buffer