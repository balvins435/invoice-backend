import datetime
import logging
import os
from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from PIL import ImageDraw as PILImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

PAGE_MARGIN = 18 * mm
CONTENT_WIDTH = A4[0] - (PAGE_MARGIN * 2)

# Design scale: one source of truth for rhythm and shape.
RADIUS = 8
BLOCK_GAP = 6 * mm
HEADER_LEFT = 120 * mm
HEADER_RIGHT = CONTENT_WIDTH - HEADER_LEFT
PILL_WIDTH = 32 * mm
PILL_FONT = 7.5
PILL_LEADING = 10
LOGO_MAX_WIDTH = 36 * mm
LOGO_MAX_HEIGHT = 10 * mm
LOGO_CHIP_PAD = 3.2 * mm

BRAND_NAVY = colors.HexColor("#0F172A")
BRAND_SURFACE = colors.HexColor("#F8FAFC")
BRAND_BORDER = colors.HexColor("#E2E8F0")
BRAND_TEXT = colors.HexColor("#0F172A")
BRAND_MUTED = colors.HexColor("#64748B")
BRAND_SOFT = colors.HexColor("#94A3B8")
BRAND_ACCENT = colors.HexColor("#2563EB")
BRAND_SUCCESS_BG = colors.HexColor("#DCFCE7")
BRAND_SUCCESS_TEXT = colors.HexColor("#166534")
BRAND_WARNING_BG = colors.HexColor("#FEF3C7")
BRAND_WARNING_TEXT = colors.HexColor("#92400E")
BRAND_DANGER_BG = colors.HexColor("#FEE2E2")
BRAND_DANGER_TEXT = colors.HexColor("#991B1B")

TEMPLATE_LETTERHEAD = "letterhead"
LETTERHEAD_INK = colors.HexColor("#111827")
LETTERHEAD_MUTED = colors.HexColor("#52525B")
LETTERHEAD_RULE = colors.HexColor("#18181B")
LETTERHEAD_HAIRLINE = colors.HexColor("#D4D4D8")
LETTERHEAD_HEAD_BG = colors.HexColor("#F4F4F5")
LETTERHEAD_LEFT = 96 * mm
LETTERHEAD_RIGHT = CONTENT_WIDTH - LETTERHEAD_LEFT


def _format_amount(value):
    return f"{value:,.2f}"


def _format_money(value, currency="KES"):
    return f"{currency} {_format_amount(value)}"


def _format_date(value):
    if value in (None, ""):
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    text = str(value).strip()
    try:
        return datetime.date.fromisoformat(text[:10]).strftime("%d %b %Y")
    except ValueError:
        return text


def _format_percent(value):
    try:
        return f"{float(value):g}%"
    except (TypeError, ValueError):
        return f"{value}%"


def _esc(value):
    """Escape business data so ampersands and angle brackets cannot break the PDF."""
    return escape(str(value))


def _safe_text(value):
    if value is None or not str(value).strip():
        return "Not provided"
    return _esc(value)


def _css(color):
    """Return a #rrggbb string for use inside paragraph markup."""
    return f"#{color.hexval()[2:]}"


def _status_colors(status):
    palette = {
        "paid": (BRAND_SUCCESS_BG, BRAND_SUCCESS_TEXT),
        "sent": (BRAND_WARNING_BG, BRAND_WARNING_TEXT),
        "draft": (colors.HexColor("#E0E7FF"), colors.HexColor("#3730A3")),
    }
    return palette.get((status or "").lower(), (BRAND_BORDER, BRAND_TEXT))


def logo_bytes(business):
    """Return the stored logo as bytes, for local and remote storage alike.

    ``FieldFile.path`` only exists on filesystem storage; a remote backend such
    as Cloudinary raises ``NotImplementedError`` for it, which used to drop the
    logo from invoice, receipt and report PDFs. Read through the storage API
    instead so the mark renders wherever the file is kept.
    """
    logo = getattr(business, "logo", None)
    if not logo:
        return None

    try:
        path = logo.path
    except (NotImplementedError, ValueError, AttributeError):
        path = None

    if path:
        try:
            if os.path.exists(path):
                with open(path, "rb") as handle:
                    return handle.read()
        except OSError as exc:
            logger.warning("Could not read the logo file at %s: %s", path, exc)

    try:
        with logo.open("rb") as handle:
            return handle.read() or None
    except Exception as exc:
        logger.warning(
            "Could not fetch the logo for business_id=%s from storage: %s",
            getattr(business, "id", None),
            exc,
        )
        return None


def _validate_logo_file(business):
    if not business.logo:
        return False

    if logo_bytes(business):
        return True

    logger.warning("Logo file missing or unreadable for business_id=%s", business.id)
    return False


def _logo_scale(logo_data, max_width, max_height):
    """Fit the logo inside the box without distorting its aspect ratio."""
    try:
        with PILImage.open(BytesIO(logo_data)) as image:
            width, height = image.size
    except Exception as exc:
        logger.warning("Unable to read logo dimensions: %s", exc)
        return max_width, max_height

    if not width or not height:
        return max_width, max_height

    scale = min(max_width / width, max_height / height)
    return width * scale, height * scale


def _logo_is_light(logo_data):
    """Sample the mark so the plate behind it can be picked for contrast."""
    try:
        with PILImage.open(BytesIO(logo_data)) as source:
            image = source.convert("RGBA")
    except Exception as exc:
        logger.warning("Unable to sample logo luminance: %s", exc)
        return False

    width, height = image.size
    step_x = max(1, width // 48)
    step_y = max(1, height // 48)
    total = 0.0
    samples = 0
    for x in range(0, width, step_x):
        for y in range(0, height, step_y):
            red, green, blue, alpha = image.getpixel((x, y))
            if alpha < 40:
                continue
            total += 0.299 * red + 0.587 * green + 0.114 * blue
            samples += 1

    if not samples:
        return False
    return (total / samples) >= 200


def _circular_logo_source(logo_data):
    """Mask the logo to a circle so `logo_shape='circle'` is honoured in the PDF."""
    try:
        with PILImage.open(BytesIO(logo_data)) as source:
            image = source.convert("RGBA")
        side = min(image.size)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))

        mask = PILImage.new("L", (side, side), 0)
        PILImageDraw.Draw(mask).ellipse((0, 0, side - 1, side - 1), fill=255)

        masked = PILImage.new("RGBA", (side, side), (0, 0, 0, 0))
        masked.paste(image, (0, 0), mask)

        buffer = BytesIO()
        masked.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as exc:
        logger.warning("Unable to build circular logo mask: %s", exc)
        return None


def _load_logo(business, log_context):
    """Return (flowable, is_circular, is_light) for the stored logo."""
    logo_data = logo_bytes(business)
    if not logo_data:
        return None, False, False

    try:
        is_circle = getattr(business, "logo_shape", "") == "circle"
        masked_source = _circular_logo_source(logo_data) if is_circle else None
        is_light = _logo_is_light(logo_data)

        if masked_source is not None:
            side = min(LOGO_MAX_WIDTH, LOGO_MAX_HEIGHT)
            width = height = side
            logo_flowable = Image(masked_source)
        else:
            width, height = _logo_scale(logo_data, LOGO_MAX_WIDTH, LOGO_MAX_HEIGHT)
            logo_flowable = Image(BytesIO(logo_data))

        logo_flowable.drawWidth = width
        logo_flowable.drawHeight = height
        logo_flowable.hAlign = "CENTER"

        logger.debug("Logo loaded successfully for %s", log_context)
        return logo_flowable, masked_source is not None, is_light
    except Exception as exc:
        logger.warning("Failed to load logo for %s: %s", log_context, str(exc), exc_info=True)
        return None, False, False


def _build_styles():
    styles = getSampleStyleSheet()
    base = styles["Normal"]

    def add(name, **kwargs):
        kwargs.setdefault("parent", base)
        styles.add(ParagraphStyle(name=name, **kwargs))

    add("Eyebrow", fontName="Helvetica-Bold", fontSize=7.5, leading=10, charSpace=1.1, textColor=BRAND_ACCENT)
    add("HeroTitle", fontName="Helvetica-Bold", fontSize=19, leading=22, alignment=0, textColor=BRAND_TEXT)
    add("HeroSub", fontName="Helvetica", fontSize=8.2, leading=12.5, alignment=0, textColor=BRAND_SOFT)
    add("MetaValue", fontName="Helvetica-Bold", fontSize=8.5, leading=12, alignment=2, textColor=BRAND_TEXT)
    add("CardLabel", fontName="Helvetica-Bold", fontSize=7.2, leading=9.5, charSpace=0.8, textColor=BRAND_MUTED)
    add("MetricLabel", fontName="Helvetica-Bold", fontSize=7.2, leading=9.5, charSpace=0.8, textColor=BRAND_MUTED)
    add("MetricValue", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=BRAND_TEXT)
    add("MetricValueAccent", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=BRAND_ACCENT)
    add("MetricCaption", fontName="Helvetica", fontSize=7.4, leading=10, textColor=BRAND_MUTED)
    add("SectionTitle", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=BRAND_TEXT)
    add("DetailLabel", fontName="Helvetica", fontSize=8.4, leading=12.5, textColor=BRAND_MUTED)
    add("DetailValue", fontName="Helvetica-Bold", fontSize=8.4, leading=12.5, alignment=2, textColor=BRAND_TEXT)
    add("InfoName", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=BRAND_TEXT)
    add("InfoLine", fontName="Helvetica", fontSize=8.4, leading=12.5, textColor=colors.HexColor("#334155"))
    add("TableHead", fontName="Helvetica-Bold", fontSize=7.2, leading=9.5, charSpace=0.7, textColor=BRAND_MUTED)
    add("TableCell", fontName="Helvetica", fontSize=9.2, leading=12.5, textColor=BRAND_TEXT)
    add("TableCellStrong", fontName="Helvetica-Bold", fontSize=9.2, leading=12.5, textColor=BRAND_TEXT)
    add("TotalLabel", fontName="Helvetica", fontSize=9, leading=12.5, textColor=BRAND_MUTED)
    add("TotalValue", fontName="Helvetica", fontSize=9, leading=12.5, alignment=2, textColor=BRAND_TEXT)
    add("GrandLabel", fontName="Helvetica-Bold", fontSize=9.5, leading=13, textColor=colors.white)
    add("GrandValue", fontName="Helvetica-Bold", fontSize=12.5, leading=15, alignment=2, textColor=colors.white)
    add("NoteText", fontName="Helvetica", fontSize=8.4, leading=12.5, textColor=colors.HexColor("#334155"))
    add("FinePrint", fontName="Helvetica", fontSize=7.4, leading=10.5, textColor=BRAND_MUTED)
    return styles


def _template_palette(template):
    if template == "minimal":
        return {
            "header_bg": colors.white,
            "header_border": BRAND_BORDER,
            "header_text": BRAND_TEXT,
            "header_soft": BRAND_MUTED,
            "header_eyebrow": BRAND_ACCENT,
            "accent": BRAND_TEXT,
            "logo_plate": BRAND_SURFACE,
            "logo_plate_dark": BRAND_NAVY,
            "logo_chip_border": BRAND_BORDER,
            "hero_bg": BRAND_SURFACE,
            "hero_text": BRAND_TEXT,
            "table_head_bg": colors.white,
            "table_head_text": BRAND_MUTED,
            "table_head_rule": BRAND_TEXT,
            "grand_bg": BRAND_TEXT,
            "grand_text": colors.white,
            "border": BRAND_BORDER,
            "surface": BRAND_SURFACE,
        }
    if template == "modern":
        accent = colors.HexColor("#047857")
        return {
            "header_bg": colors.HexColor("#064E3B"),
            "header_border": None,
            "header_text": colors.white,
            "header_soft": colors.HexColor("#A7F3D0"),
            "header_eyebrow": colors.HexColor("#6EE7B7"),
            "accent": accent,
            "logo_plate": colors.white,
            "logo_plate_dark": None,
            "logo_chip_border": colors.HexColor("#D1FAE5"),
            "hero_bg": colors.HexColor("#ECFDF5"),
            "hero_text": colors.HexColor("#065F46"),
            "table_head_bg": colors.HexColor("#F0FDF4"),
            "table_head_text": colors.HexColor("#065F46"),
            "table_head_rule": accent,
            "grand_bg": accent,
            "grand_text": colors.white,
            "border": colors.HexColor("#D1FAE5"),
            "surface": colors.white,
        }
    if template == TEMPLATE_LETTERHEAD:
        return {
            "header_bg": colors.white,
            "header_border": LETTERHEAD_RULE,
            "header_text": LETTERHEAD_INK,
            "header_soft": LETTERHEAD_MUTED,
            "header_eyebrow": LETTERHEAD_MUTED,
            "accent": LETTERHEAD_RULE,
            "logo_plate": None,
            "logo_plate_dark": None,
            "logo_chip_border": None,
            "hero_bg": colors.white,
            "hero_text": LETTERHEAD_INK,
            "table_head_bg": LETTERHEAD_HEAD_BG,
            "table_head_text": LETTERHEAD_INK,
            "table_head_rule": LETTERHEAD_RULE,
            "grand_bg": colors.white,
            "grand_text": LETTERHEAD_INK,
            "border": LETTERHEAD_HAIRLINE,
            "surface": colors.white,
        }
    return {
        "header_bg": BRAND_NAVY,
        "header_border": None,
        "header_text": colors.white,
        "header_soft": BRAND_SOFT,
        "header_eyebrow": colors.HexColor("#93C5FD"),
        "accent": BRAND_ACCENT,
        "logo_plate": colors.white,
        "logo_plate_dark": None,
        "logo_chip_border": None,
        "hero_bg": colors.HexColor("#EFF6FF"),
        "hero_text": colors.HexColor("#1D4ED8"),
        "table_head_bg": BRAND_SURFACE,
        "table_head_text": BRAND_MUTED,
        "table_head_rule": BRAND_ACCENT,
        "grand_bg": BRAND_NAVY,
        "grand_text": colors.white,
        "border": BRAND_BORDER,
        "surface": BRAND_SURFACE,
    }


def _apply_invoice_template_styles(styles, palette):
    styles["Eyebrow"].textColor = palette["header_eyebrow"]
    styles["HeroTitle"].textColor = palette["header_text"]
    styles["HeroSub"].textColor = palette["header_soft"]
    styles["MetaValue"].textColor = palette["header_text"]
    styles["MetricValueAccent"].textColor = palette["hero_text"]
    styles["TableHead"].textColor = palette["table_head_text"]
    styles["GrandLabel"].textColor = palette["grand_text"]
    styles["GrandValue"].textColor = palette["grand_text"]
    return styles


TEMPLATE_LAYOUTS = {
    "classic": "hero",
    "modern": "hero",
    "minimal": "hero",
    TEMPLATE_LETTERHEAD: "letterhead",
}

TEMPLATE_META = (
    ("classic", "Classic", "Deep navy header with a bold, structured summary strip."),
    ("modern", "Modern", "Fresh emerald header for a confident, contemporary look."),
    ("minimal", "Minimal", "Quiet whitespace with hairline rules and understated type."),
    (TEMPLATE_LETTERHEAD, "Letterhead", "Timeless letterhead with a ruled, bordered table."),
)

TEMPLATE_IDS = tuple(entry[0] for entry in TEMPLATE_META)


def _hex_color(value):
    if value is None:
        return None
    red, green, blue = (max(0.0, min(1.0, channel)) for channel in value.rgb())
    return "#{:02X}{:02X}{:02X}".format(
        int(round(red * 255)),
        int(round(green * 255)),
        int(round(blue * 255)),
    )


def invoice_template_catalogue():
    """Describe every invoice template so the UI can render real samples."""
    catalogue = []
    for template_id, name, description in TEMPLATE_META:
        palette = _template_palette(template_id)
        catalogue.append(
            {
                "id": template_id,
                "name": name,
                "description": description,
                "layout": TEMPLATE_LAYOUTS[template_id],
                "palette": {
                    key: _hex_color(value)
                    for key, value in palette.items()
                    if value is not None
                },
            }
        )
    return catalogue


def resolve_invoice_template(invoice, template=None):
    """Resolve a render template: explicit choice, invoice, business default, classic."""
    business = getattr(invoice, "business", None)
    candidates = (
        template,
        getattr(invoice, "template", None),
        getattr(business, "default_invoice_template", None),
    )
    for candidate in candidates:
        normalized = str(candidate or "").strip().lower()
        if normalized in TEMPLATE_IDS:
            return normalized
    return "classic"


def _build_pill(text, background, text_color, width=PILL_WIDTH):
    label = Paragraph(
        f"&#8226;&nbsp;&nbsp;{escape(str(text)).upper()}",
        ParagraphStyle(
            "PillText",
            fontName="Helvetica-Bold",
            fontSize=PILL_FONT,
            leading=PILL_LEADING,
            charSpace=0.6,
            textColor=text_color,
            alignment=1,
        ),
    )
    height = PILL_LEADING + 9
    pill = Table([[label]], colWidths=[width], rowHeights=[height])
    pill.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("ROUNDEDCORNERS", [height / 2.0] * 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    pill.hAlign = "RIGHT"
    return pill


def _build_logo_chip(logo, background, border, radius=6):
    chip = Table(
        [[logo]],
        colWidths=[logo.drawWidth + 2 * LOGO_CHIP_PAD],
        rowHeights=[logo.drawHeight + 2 * LOGO_CHIP_PAD],
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("ROUNDEDCORNERS", [radius] * 4),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]
    if border is not None:
        commands.append(("BOX", (0, 0), (-1, -1), 0.6, border))
    chip.setStyle(TableStyle(commands))
    return chip


def _build_brand_text(eyebrow, title, contact_lines, styles, width):
    rows = [
        [Paragraph(escape(eyebrow).upper(), styles["Eyebrow"])],
        [Paragraph(escape(title), styles["HeroTitle"])],
    ]
    for line in contact_lines:
        rows.append([Paragraph(line, styles["HeroSub"])])

    text = Table(rows, colWidths=[width])
    text.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (0, 0), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return text


def _build_header_meta(badge_text, badge_background, badge_color, meta_pairs, styles, palette, width):
    rows = [[_build_pill(badge_text, badge_background, badge_color)]]
    rows.append([Spacer(1, 4.5 * mm)])
    label_color = _css(palette["header_soft"])
    for label, value in meta_pairs:
        rows.append(
            [
                Paragraph(
                    f"<font size='6.6' color='{label_color}'>{escape(label).upper()}</font>"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;{escape(value)}",
                    styles["MetaValue"],
                )
            ]
        )

    meta = Table(rows, colWidths=[width])
    meta.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return meta


def _build_header(eyebrow, title, contact_lines, meta_pairs, badge_text, badge_background, badge_color, business, styles, log_context, palette):
    logo, is_circular, is_light = _load_logo(business, log_context)
    left_pad, right_pad = 22, 10
    content_width = HEADER_LEFT - left_pad - right_pad

    if logo is not None:
        light_logo = is_light
        plate = palette["logo_plate_dark"] if light_logo else palette["logo_plate"]
        if plate is None:
            logo.hAlign = "LEFT"
            chip = logo
            chip_width = logo.drawWidth
        else:
            border = None if light_logo else palette["logo_chip_border"]
            chip_width = logo.drawWidth + 2 * LOGO_CHIP_PAD
            radius = chip_width / 2.0 if is_circular else 6
            chip = _build_logo_chip(logo, plate, border, radius)
        gutter = 5 * mm
        text_width = content_width - chip_width - gutter
        brand = Table(
            [[chip, _build_brand_text(eyebrow, title, contact_lines, styles, text_width)]],
            colWidths=[chip_width + gutter, text_width],
        )
        brand.setStyle(
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
    else:
        brand = _build_brand_text(eyebrow, title, contact_lines, styles, content_width)

    meta = _build_header_meta(
        badge_text,
        badge_background,
        badge_color,
        meta_pairs,
        styles,
        palette,
        HEADER_RIGHT - right_pad,
    )

    header = Table([[brand, meta]], colWidths=[HEADER_LEFT, HEADER_RIGHT])
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), palette["header_bg"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), left_pad),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), right_pad),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("ROUNDEDCORNERS", [RADIUS] * 4),
    ]
    if palette["header_border"] is not None:
        commands.append(("BOX", (0, 0), (-1, -1), 0.8, palette["header_border"]))
    header.setStyle(TableStyle(commands))
    return header


def _build_summary_strip(cells, styles, palette):
    """A single divided card: (label, value, caption, emphasised)."""
    width = CONTENT_WIDTH / 3
    labels, values, captions = [], [], []
    for label, value, caption, emphasised in cells:
        labels.append(Paragraph(escape(label).upper(), styles["MetricLabel"]))
        value_style = styles["MetricValueAccent" if emphasised else "MetricValue"]
        values.append(Paragraph(escape(value), value_style))
        captions.append(Paragraph(escape(caption or ""), styles["MetricCaption"]))

    strip = Table([labels, values, captions], colWidths=[width] * 3)
    strip.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), palette["hero_bg"]),
                ("BACKGROUND", (1, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, BRAND_BORDER),
                ("LINEBEFORE", (1, 0), (1, -1), 0.8, BRAND_BORDER),
                ("LINEBEFORE", (2, 0), (2, -1), 0.8, BRAND_BORDER),
                ("ROUNDEDCORNERS", [RADIUS] * 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
                ("TOPPADDING", (0, 2), (-1, 2), 0),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return strip


def _card_shell(rows, width):
    card = Table(rows, colWidths=[width])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, BRAND_BORDER),
                ("ROUNDEDCORNERS", [RADIUS] * 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return card


def _build_info_card(title, entries, styles, width):
    """entries: (style name, already-escaped text) with None for a breather row."""
    rows = [[Paragraph(escape(title).upper(), styles["CardLabel"])]]
    for style_name, text in entries:
        if text is None:
            rows.append([Spacer(1, 2.5 * mm)])
        else:
            rows.append([Paragraph(text, styles[style_name])])
    return _card_shell(rows, width)


def _build_details_card(title, pairs, styles, width):
    label_width = width * 0.54
    rows = [[Paragraph(escape(title).upper(), styles["CardLabel"]), ""]]
    for label, value in pairs:
        rows.append(
            [
                Paragraph(escape(label), styles["DetailLabel"]),
                Paragraph(escape(value), styles["DetailValue"]),
            ]
        )

    card = Table(rows, colWidths=[label_width, width - label_width])
    card.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, BRAND_BORDER),
                ("ROUNDEDCORNERS", [RADIUS] * 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return card


def _build_items_table(invoice, styles, palette):
    currency = invoice.currency or "KES"
    rows = [
        [
            Paragraph("Description", styles["TableHead"]),
            Paragraph("Qty", styles["TableHead"]),
            Paragraph("Unit price", styles["TableHead"]),
            Paragraph("Line total", styles["TableHead"]),
        ]
    ]

    items = list(invoice.items.all())
    for item in items:
        rows.append(
            [
                Paragraph(escape(item.description), styles["TableCell"]),
                Paragraph(escape(str(item.quantity)), styles["TableCell"]),
                Paragraph(escape(_format_money(item.unit_price, currency)), styles["TableCell"]),
                Paragraph(escape(_format_money(item.total, currency)), styles["TableCellStrong"]),
            ]
        )

    if not items:
        rows.append([Paragraph("No line items on this invoice.", styles["TableCell"]), "", "", ""])

    table = Table(rows, colWidths=[88 * mm, 16 * mm, 34 * mm, 36 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["table_head_bg"]),
                ("LINEBELOW", (0, 0), (-1, 0), 1, palette["table_head_rule"]),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, BRAND_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
                ("TOPPADDING", (0, 1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _build_totals_card(rows, styles, palette, width=86 * mm):
    label_width = width * 0.46
    table_rows = []
    for label, value, strong in rows:
        table_rows.append(
            [
                Paragraph(escape(label), styles["GrandLabel" if strong else "TotalLabel"]),
                Paragraph(escape(value), styles["GrandValue" if strong else "TotalValue"]),
            ]
        )

    card = Table(table_rows, colWidths=[label_width, width - label_width])
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), palette["grand_bg"]),
        ("BOX", (0, 0), (-1, -1), 0.8, BRAND_BORDER),
        ("ROUNDEDCORNERS", [RADIUS] * 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, -1), (-1, -1), 11),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -2), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 9),
    ]
    if len(table_rows) == 1:
        commands[-2:] = [
            ("TOPPADDING", (0, 0), (-1, 0), 11),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 11),
        ]
    card.setStyle(TableStyle(commands))
    return card


def _build_note_card(title, lines, styles, palette, width, bar=3.2 * mm):
    rows = [[Paragraph(escape(title).upper(), styles["CardLabel"])]]
    for line in lines:
        rows.append([Paragraph(line, styles["NoteText"])])

    content_width = width - bar - 28
    content = Table(rows, colWidths=[content_width])
    content.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (0, 0), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    card = Table([["", content]], colWidths=[bar, width - bar])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), palette["accent"]),
                ("BACKGROUND", (1, 0), (1, -1), BRAND_SURFACE),
                ("ROUNDEDCORNERS", [7, 7, 7, 7]),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (1, 0), (1, 0), 14),
                ("RIGHTPADDING", (1, 0), (1, 0), 14),
                ("TOPPADDING", (1, 0), (1, 0), 11),
                ("BOTTOMPADDING", (1, 0), (1, 0), 12),
            ]
        )
    )
    return card


def _make_footer(left_text):
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BRAND_BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(PAGE_MARGIN, 15 * mm, A4[0] - PAGE_MARGIN, 15 * mm)
        canvas.setFont("Helvetica", 7.4)
        canvas.setFillColor(BRAND_MUTED)
        canvas.drawString(PAGE_MARGIN, 11 * mm, left_text)
        canvas.drawRightString(A4[0] - PAGE_MARGIN, 11 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    return _footer


def _business_contact_lines(business):
    primary = [value for value in (business.email, business.phone) if value]
    lines = []
    if primary:
        lines.append("&nbsp;&nbsp;&nbsp;&middot;&nbsp;&nbsp;&nbsp;".join(_esc(value) for value in primary))
    if business.address:
        lines.append("<br/>".join(_esc(line) for line in str(business.address).splitlines() if line.strip()))
    return lines


def _new_document(buffer, title, author):
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=PAGE_MARGIN,
        leftMargin=PAGE_MARGIN,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=title,
        author=author,
    )


def _flush_row(cells):
    """Lay blocks side by side, flush to the content edges."""
    row = Table([[flowable for _, flowable in cells]], colWidths=[width for width, _ in cells])
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return row


def _letterhead_plain_style():
    return TableStyle(
        [
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )


def _letterhead_styles(styles):
    ink = LETTERHEAD_INK
    add = styles.add
    add(ParagraphStyle("LetterheadBrand", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=ink))
    add(ParagraphStyle("LetterheadContact", parent=styles["Normal"], fontName="Helvetica", fontSize=8.6, leading=12.4, textColor=LETTERHEAD_MUTED))
    add(ParagraphStyle("LetterheadTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=26, leading=30, alignment=2, textColor=ink))
    add(ParagraphStyle("LetterheadTitleSub", parent=styles["Normal"], fontName="Helvetica", fontSize=8.6, leading=12.4, alignment=2, textColor=LETTERHEAD_MUTED))
    add(ParagraphStyle("LetterheadLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.6, leading=11, charSpace=0.9, textColor=LETTERHEAD_MUTED))
    add(ParagraphStyle("LetterheadBillName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11.5, leading=15.5, textColor=ink))
    add(ParagraphStyle("LetterheadBillLine", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=LETTERHEAD_MUTED))
    add(ParagraphStyle("LetterheadMetaLabel", parent=styles["Normal"], fontName="Helvetica", fontSize=8.6, leading=14, alignment=2, textColor=LETTERHEAD_MUTED))
    add(ParagraphStyle("LetterheadMetaValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.6, leading=14, textColor=ink))
    add(ParagraphStyle("LetterheadHead", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.2, leading=11, textColor=ink))
    add(ParagraphStyle("LetterheadCell", parent=styles["Normal"], fontName="Helvetica", fontSize=9.2, leading=12.6, textColor=ink))
    add(ParagraphStyle("LetterheadCellStrong", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.2, leading=12.6, textColor=ink))
    add(ParagraphStyle("LetterheadTotalLabel", parent=styles["Normal"], fontName="Helvetica", fontSize=9.2, leading=14, alignment=2, textColor=LETTERHEAD_MUTED))
    add(ParagraphStyle("LetterheadTotalValue", parent=styles["Normal"], fontName="Helvetica", fontSize=9.2, leading=14, alignment=2, textColor=ink))
    add(ParagraphStyle("LetterheadTotalDueLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=15, alignment=2, textColor=ink))
    add(ParagraphStyle("LetterheadTotalDueValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, alignment=2, textColor=ink))
    add(ParagraphStyle("LetterheadNote", parent=styles["Normal"], fontName="Helvetica", fontSize=8.4, leading=12.6, textColor=LETTERHEAD_MUTED))
    return styles


def _coerce_date(value):
    """Accept a real date or the ISO strings used by API payloads."""
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _letterhead_contact_lines(business):
    lines = []
    for line in str(business.address or "").splitlines():
        if line.strip():
            lines.append(escape(line.strip()))
    contact = "&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(
        escape(str(value)) for value in (business.phone, business.email) if value
    )
    if contact:
        lines.append(contact)
    return lines


def _letterhead_brand(logo, is_light, business_name, contact_lines, styles, width):
    text_rows = [[Paragraph(escape(business_name), styles["LetterheadBrand"])]]
    for line in contact_lines:
        text_rows.append([Paragraph(line, styles["LetterheadContact"])])

    if logo is None:
        block = Table(text_rows, colWidths=[width])
        block.setStyle(_letterhead_plain_style())
        return block

    max_mark = 20 * mm
    scale = min(1.0, max_mark / max(logo.drawWidth, 1), max_mark / max(logo.drawHeight, 1))
    logo.drawWidth *= scale
    logo.drawHeight *= scale
    logo.hAlign = "CENTER"

    if is_light:
        mark = _build_logo_chip(logo, BRAND_NAVY, None, 6)
        mark_width = logo.drawWidth + 2 * LOGO_CHIP_PAD
    else:
        mark = logo
        mark_width = logo.drawWidth

    gutter = 4.5 * mm
    text_width = width - mark_width - gutter
    text = Table(text_rows, colWidths=[text_width])
    text.setStyle(_letterhead_plain_style())

    block = Table([[mark, text]], colWidths=[mark_width + gutter, text_width])
    style = _letterhead_plain_style()
    style.add("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    block.setStyle(style)
    return block


def _letterhead_parties(invoice, styles):
    bill_rows = [[Paragraph("Bill To", styles["LetterheadLabel"])]]
    bill_rows.append([Paragraph(escape(invoice.client_name or ""), styles["LetterheadBillName"])])
    if invoice.client_email:
        bill_rows.append([Paragraph(escape(invoice.client_email), styles["LetterheadBillLine"])])
    bill = Table(bill_rows, colWidths=[LETTERHEAD_LEFT])
    bill.setStyle(_letterhead_plain_style())

    terms = "Due on receipt"
    issue_date = _coerce_date(invoice.issue_date)
    due_date = _coerce_date(invoice.due_date)
    if issue_date and due_date:
        days = (due_date - issue_date).days
        if days > 0:
            terms = f"Net {days}"

    pairs = [
        ("Invoice Number", invoice.invoice_number),
        ("Date", _format_date(invoice.issue_date)),
        ("Due Date", _format_date(invoice.due_date)),
        ("Terms", terms),
        ("Status", (invoice.status or "draft").title()),
    ]
    meta_width = 62 * mm
    meta = Table(
        [
            [
                Paragraph(escape(str(label)), styles["LetterheadMetaLabel"]),
                Paragraph(escape(str(value)), styles["LetterheadMetaValue"]),
            ]
            for label, value in pairs
        ],
        colWidths=[meta_width * 0.58, meta_width * 0.42],
    )
    meta.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("RIGHTPADDING", (0, 0), (0, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    meta.hAlign = "RIGHT"

    return _flush_row([(LETTERHEAD_LEFT, bill), (LETTERHEAD_RIGHT, meta)])


def _letterhead_items_table(invoice, styles):
    currency = invoice.currency or "KES"
    rows = [
        [
            Paragraph("Description", styles["LetterheadHead"]),
            Paragraph("Quantity", styles["LetterheadHead"]),
            Paragraph("Unit price", styles["LetterheadHead"]),
            Paragraph("Amount", styles["LetterheadHead"]),
        ]
    ]
    items = list(invoice.items.all())
    for item in items:
        rows.append(
            [
                Paragraph(escape(item.description), styles["LetterheadCell"]),
                Paragraph(escape(str(item.quantity)), styles["LetterheadCell"]),
                Paragraph(escape(_format_money(item.unit_price, currency)), styles["LetterheadCell"]),
                Paragraph(escape(_format_money(item.total, currency)), styles["LetterheadCellStrong"]),
            ]
        )
    if not items:
        rows.append([Paragraph("No line items on this invoice.", styles["LetterheadCell"]), "", "", ""])

    table = Table(
        rows,
        colWidths=[CONTENT_WIDTH - 84 * mm, 20 * mm, 31 * mm, 33 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LETTERHEAD_HEAD_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, LETTERHEAD_HAIRLINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LETTERHEAD_HAIRLINE),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, LETTERHEAD_RULE),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 9.5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 9.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _letterhead_totals(invoice, styles, business):
    currency = invoice.currency or "KES"
    rows = [
        ("Subtotal", _format_money(invoice.subtotal, currency)),
        (f"VAT ({_format_percent(business.tax_rate)})", _format_money(invoice.tax_amount, currency)),
    ]
    if invoice.amount_paid:
        rows.append(("Amount paid", _format_money(invoice.amount_paid, currency)))
    rows.append(
        ("Total Due", "Paid in full" if invoice.balance_due == 0 else _format_money(invoice.balance_due, currency))
    )

    table_rows = []
    for index, (label, value) in enumerate(rows):
        last = index == len(rows) - 1
        table_rows.append(
            [
                Paragraph(escape(label), styles["LetterheadTotalDueLabel" if last else "LetterheadTotalLabel"]),
                Paragraph(escape(value), styles["LetterheadTotalDueValue" if last else "LetterheadTotalValue"]),
            ]
        )

    width = 78 * mm
    commands = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEABOVE", (0, -1), (-1, -1), 1.0, LETTERHEAD_RULE),
        ("TOPPADDING", (0, -1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 2),
    ]
    if len(rows) > 1:
        commands.extend(
            [
                ("TOPPADDING", (0, 0), (-1, -2), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 4),
            ]
        )
    table = Table(table_rows, colWidths=[width * 0.5, width * 0.5])
    table.setStyle(TableStyle(commands))
    table.hAlign = "RIGHT"
    return table


def _letterhead_notes(invoice, styles):
    currency = invoice.currency or "KES"
    lines = [
        f"This invoice is currently <b>{_esc(invoice.status)}</b> with an outstanding balance of "
        f"<b>{_esc(_format_money(invoice.balance_due, currency))}</b>."
    ]
    if invoice.tax_invoice_number:
        lines.append(f"KRA eTIMS tax invoice number: <b>{_esc(invoice.tax_invoice_number)}</b>.")
    lines.append("Thank you for your business. Please quote the invoice number as your payment reference.")

    rows = [[Paragraph("Notes", styles["LetterheadLabel"])]]
    for line in lines:
        rows.append([Paragraph(line, styles["LetterheadNote"])])
    block = Table(rows, colWidths=[118 * mm])
    block.setStyle(_letterhead_plain_style())
    return block


def _build_letterhead_pdf(invoice, styles, buffer, business_name):
    _letterhead_styles(styles)
    business = invoice.business

    doc = _new_document(buffer, f"Invoice {invoice.invoice_number}", business_name)

    logo, _is_circular, is_light = _load_logo(
        business,
        f"business_id={invoice.business_id}, invoice_number={invoice.invoice_number}",
    )
    brand = _letterhead_brand(
        logo,
        is_light,
        business_name,
        _letterhead_contact_lines(business),
        styles,
        LETTERHEAD_LEFT,
    )
    title = Table(
        [
            [Paragraph("Invoice", styles["LetterheadTitle"])],
            [Paragraph(escape(invoice.invoice_number), styles["LetterheadTitleSub"])],
        ],
        colWidths=[LETTERHEAD_RIGHT],
    )
    title.setStyle(_letterhead_plain_style())

    story = [
        _flush_row([(LETTERHEAD_LEFT, brand), (LETTERHEAD_RIGHT, title)]),
        Spacer(1, 5 * mm),
        HRFlowable(width="100%", thickness=1.1, color=LETTERHEAD_RULE, spaceBefore=0, spaceAfter=0),
        Spacer(1, 7 * mm),
        _letterhead_parties(invoice, styles),
        Spacer(1, 9 * mm),
        _letterhead_items_table(invoice, styles),
        Spacer(1, 4 * mm),
        _letterhead_totals(invoice, styles, business),
        Spacer(1, 10 * mm),
        _letterhead_notes(invoice, styles),
    ]

    footer_text = f"{business_name}  \u00b7  Invoice {invoice.invoice_number}"
    doc.build(story, onFirstPage=_make_footer(footer_text), onLaterPages=_make_footer(footer_text))
    buffer.seek(0)
    return buffer


def generate_invoice_pdf(invoice, template=None):
    styles = _build_styles()
    selected_template = resolve_invoice_template(invoice, template)
    palette = _template_palette(selected_template)
    _apply_invoice_template_styles(styles, palette)

    business = invoice.business
    business_name = business.display_name or business.name
    buffer = BytesIO()

    if selected_template == TEMPLATE_LETTERHEAD:
        return _build_letterhead_pdf(invoice, styles, buffer, business_name)

    currency = invoice.currency or "KES"
    amount_due = _format_money(invoice.balance_due, currency)
    settled = invoice.balance_due == 0

    doc = _new_document(buffer, f"Invoice {invoice.invoice_number}", business_name)

    badge_background, badge_color = _status_colors(invoice.status)

    header = _build_header(
        eyebrow=f"Invoice {invoice.invoice_number}",
        title=business_name,
        contact_lines=_business_contact_lines(business),
        meta_pairs=[
            ("Issued", _format_date(invoice.issue_date)),
            ("Due", _format_date(invoice.due_date)),
        ],
        badge_text=invoice.status,
        badge_background=badge_background,
        badge_color=badge_color,
        business=business,
        styles=styles,
        log_context=f"business_id={business.id}, invoice_number={invoice.invoice_number}",
        palette=palette,
    )

    summary = _build_summary_strip(
        [
            (
                "Amount due",
                amount_due,
                "Settled in full" if settled else f"Payable by {_format_date(invoice.due_date)}",
                True,
            ),
            ("Amount paid", _format_money(invoice.amount_paid, currency), None, False),
            ("Invoice total", _format_money(invoice.total_amount, currency), None, False),
        ],
        styles,
        palette,
    )

    items = list(invoice.items.all())
    bill_to = _build_info_card(
        "Bill to",
        [
            ("InfoName", _safe_text(invoice.client_name)),
            ("InfoLine", _safe_text(invoice.client_email)),
            (None, None),
        ],
        styles,
        85 * mm,
    )

    details = _build_details_card(
        "Invoice details",
        [
            ("Status", (invoice.status or "draft").title()),
            ("Currency", currency),
            ("Line items", str(len(items))),
        ],
        styles,
        85 * mm,
    )

    parties = _flush_row([(85 * mm, bill_to), (4 * mm, None), (85 * mm, details)])

    totals = _build_totals_card(
        [
            ("Subtotal", _format_money(invoice.subtotal, currency), False),
            (f"VAT ({_format_percent(business.tax_rate)})", _format_money(invoice.tax_amount, currency), False),
            ("Total", _format_money(invoice.total_amount, currency), True),
        ],
        styles,
        palette,
    )

    note_lines = [
        f"This invoice is currently <b>{_esc(invoice.status)}</b> with an outstanding balance of "
        f"<b>{_esc(amount_due)}</b>."
    ]
    if invoice.tax_invoice_number:
        note_lines.append(f"KRA eTIMS tax invoice number: <b>{_esc(invoice.tax_invoice_number)}</b>.")
    note = _build_note_card("Payment summary", note_lines, styles, palette, 88 * mm)

    closing = KeepTogether(
        [
            _flush_row([(88 * mm, note), (86 * mm, totals)]),
            Spacer(1, 5 * mm),
            Paragraph(
                "Thank you for your business. Please quote the invoice number as your payment reference.",
                styles["FinePrint"],
            ),
        ]
    )

    story = [
        header,
        Spacer(1, BLOCK_GAP),
        summary,
        Spacer(1, BLOCK_GAP),
        parties,
        Spacer(1, 7 * mm),
        Paragraph("Items", styles["SectionTitle"]),
        Spacer(1, 3 * mm),
        _build_items_table(invoice, styles, palette),
        Spacer(1, 7 * mm),
        closing,
    ]

    footer_text = f"{business_name}  ·  Invoice {invoice.invoice_number}"
    doc.build(story, onFirstPage=_make_footer(footer_text), onLaterPages=_make_footer(footer_text))
    buffer.seek(0)
    return buffer


def generate_receipt_pdf(receipt):
    styles = _build_styles()
    invoice = receipt.invoice
    business = invoice.business
    business_name = business.display_name or business.name
    currency = receipt.currency or invoice.currency or "KES"
    palette = _template_palette(resolve_invoice_template(invoice))
    _apply_invoice_template_styles(styles, palette)

    buffer = BytesIO()
    doc = _new_document(buffer, f"Receipt {receipt.receipt_number}", business_name)

    balance = invoice.balance_due
    receipt_message = (
        "This payment settles the invoice in full."
        if balance == 0
        else f"This payment was recorded successfully. Remaining balance: {_format_money(balance, currency)}."
    )

    header = _build_header(
        eyebrow=f"Receipt {receipt.receipt_number}",
        title=business_name,
        contact_lines=_business_contact_lines(business),
        meta_pairs=[
            ("Payment date", _format_date(receipt.payment_date)),
            ("Invoice", invoice.invoice_number),
        ],
        badge_text="received",
        badge_background=BRAND_SUCCESS_BG,
        badge_color=BRAND_SUCCESS_TEXT,
        business=business,
        styles=styles,
        log_context=f"receipt_number={receipt.receipt_number}, invoice_number={invoice.invoice_number}",
        palette=palette,
    )

    summary = _build_summary_strip(
        [
            (
                "Amount received",
                _format_money(receipt.amount_paid, currency),
                _format_date(receipt.payment_date),
                True,
            ),
            ("Invoice total", _format_money(invoice.total_amount, currency), None, False),
            ("Balance due", _format_money(balance, currency), None, False),
        ],
        styles,
        palette,
    )

    received_from = _build_info_card(
        "Received from",
        [
            ("InfoName", _safe_text(invoice.client_name)),
            ("InfoLine", _safe_text(invoice.client_email)),
            (None, None),
        ],
        styles,
        85 * mm,
    )

    details = _build_details_card(
        "Receipt details",
        [
            ("Method", receipt.get_payment_method_display()),
            ("Reference", _safe_text(receipt.reference)),
            ("Invoice", invoice.invoice_number),
        ],
        styles,
        85 * mm,
    )

    parties = _flush_row([(85 * mm, received_from), (4 * mm, None), (85 * mm, details)])

    allocation = _build_totals_card(
        [
            ("Payment date", _format_date(receipt.payment_date), False),
            ("Amount applied", _format_money(receipt.amount_paid, currency), False),
            ("Balance remaining", _format_money(balance, currency), True),
        ],
        styles,
        palette,
    )

    note_lines = [receipt_message]
    if receipt.notes:
        note_lines.append(f"Notes: {_esc(receipt.notes)}")
    note = _build_note_card("Payment note", note_lines, styles, palette, 88 * mm)

    closing = KeepTogether(
        [
            _flush_row([(88 * mm, note), (86 * mm, allocation)]),
            Spacer(1, 5 * mm),
            Paragraph(
                "Keep this receipt for your records. It confirms the payment captured in SmartInvoice.",
                styles["FinePrint"],
            ),
        ]
    )

    story = [
        header,
        Spacer(1, BLOCK_GAP),
        summary,
        Spacer(1, BLOCK_GAP),
        parties,
        Spacer(1, 7 * mm),
        closing,
    ]

    footer_text = f"{business_name}  ·  Receipt {receipt.receipt_number}"
    doc.build(story, onFirstPage=_make_footer(footer_text), onLaterPages=_make_footer(footer_text))
    buffer.seek(0)
    return buffer