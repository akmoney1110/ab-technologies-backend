from io import BytesIO
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    PageBreak,
)


# ============================================================
# HELPERS
# ============================================================

PRIMARY = colors.HexColor("#111827")
SECONDARY = colors.HexColor("#4B5563")
MUTED = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F9FAFB")
LIGHTER = colors.HexColor("#F3F4F6")
BORDER = colors.HexColor("#E5E7EB")
ACCENT = colors.HexColor("#2563EB")
ACCENT_LIGHT = colors.HexColor("#EFF6FF")
SUCCESS = colors.HexColor("#059669")
SUCCESS_LIGHT = colors.HexColor("#ECFDF5")
WHITE = colors.white


def _safe_text(value):
    """
    Safely convert arbitrary values to text suitable for ReportLab Paragraph.
    """
    if value is None:
        return ""

    if isinstance(value, bool):
        return "Yes" if value else "No"

    return escape(str(value))


def _money(value):
    """
    Convert a value into Decimal safely.
    """
    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _format_money(value, currency="NGN"):
    amount = _money(value)
    return f"{currency} {amount:,.2f}"


def _normalise_list(value):
    """
    Convert common proposal data formats into a list.

    Supports:
        - None
        - string
        - list
        - tuple
        - queryset-like values
        - dictionaries
    """
    if not value:
        return []

    if isinstance(value, str):
        lines = [
            line.strip()
            for line in value.splitlines()
            if line.strip()
        ]

        return lines or [value.strip()]

    if isinstance(value, dict):
        text = (
            value.get("name")
            or value.get("title")
            or value.get("label")
            or value.get("description")
            or ""
        )

        return [str(text).strip()] if str(text).strip() else []

    if isinstance(value, (list, tuple)):
        result = []

        for item in value:
            if isinstance(item, dict):
                text = (
                    item.get("name")
                    or item.get("title")
                    or item.get("label")
                    or item.get("description")
                    or ""
                )
            else:
                text = str(item)

            text = str(text).strip()

            if text:
                result.append(text)

        return result

    try:
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
    except TypeError:
        return [str(value).strip()]


def _add_bullet_list(
    story,
    items,
    normal_style,
    bullet_style,
):
    for item in items:
        story.append(
            Paragraph(
                f"• {_safe_text(item)}",
                bullet_style,
            )
        )

        story.append(
            Spacer(1, 1.2 * mm)
        )


def _get_quotation_from_proposal(proposal):
    """
    Get the quotation attached to the proposal.

    Priority:
        1. Accepted pricing snapshot
        2. quote_request relation

    This means the accepted PDF can preserve the exact quotation
    accepted by the client instead of relying on a later-mutated
    QuoteRequest.
    """

    pricing_snapshot = getattr(
        proposal,
        "pricing_snapshot",
        None,
    )

    if isinstance(pricing_snapshot, dict):

        accepted_scope = pricing_snapshot.get(
            "accepted_scope"
        )

        if isinstance(accepted_scope, dict):

            quotation = accepted_scope.get(
                "quotation"
            )

            if isinstance(quotation, dict):
                return quotation

        quotation = pricing_snapshot.get(
            "quotation"
        )

        if isinstance(quotation, dict):
            return quotation

    quote_request = getattr(
        proposal,
        "quote_request",
        None,
    )

    if not quote_request:
        return None

    items = []

    for item in quote_request.items.all().order_by(
        "created_at"
    ):
        items.append(
            {
                "id": str(item.id),
                "category": item.category,
                "name": item.name,
                "brand": item.brand,
                "model": item.model,
                "description": item.description,
                "specifications": (
                    item.specifications
                    if isinstance(
                        item.specifications,
                        dict,
                    )
                    else {}
                ),
                "quantity": item.quantity,
                "unit_price": (
                    str(item.unit_price)
                    if item.unit_price is not None
                    else None
                ),
                "total_price": (
                    str(item.total_price)
                    if item.total_price is not None
                    else None
                ),
                "included": True,
            }
        )

    currency = (
        getattr(
            quote_request,
            "currency",
            None,
        )
        or "NGN"
    )

    return {
        "id": str(quote_request.id),
        "title": quote_request.title,
        "request_type": quote_request.request_type,
        "description": quote_request.description,
        "purpose": quote_request.purpose,
        "notes": quote_request.notes,
        "currency": currency,
        "items": items,
        "subtotal": str(
            quote_request.subtotal
        ),
        "discount": str(
            quote_request.discount
        ),
        "tax": str(
            quote_request.tax
        ),
        "delivery_fee": str(
            quote_request.delivery_fee
        ),
        "total": str(
            quote_request.total
        ),
    }


def _get_screen_items(proposal):
    """
    Normalize proposal screens into a consistent structure:

        {
            "name": "...",
            "description": "...",
            "purpose": "..."
        }

    Supports:
        - Django RelatedManager
        - Django QuerySet
        - ProposalScreen model instances
        - dictionaries
        - strings
        - lists / tuples
        - legacy proposed_screens / screen_list values

    The function is intentionally defensive because proposal screen data
    may come from either persisted database records or older JSON-style
    proposal data.
    """

    # --------------------------------------------------------
    # 1. FIND THE SCREEN SOURCE
    # --------------------------------------------------------

    screens = getattr(
        proposal,
        "screens",
        None,
    )

    if screens is None:
        screens = getattr(
            proposal,
            "proposed_screens",
            None,
        )

    if screens is None:
        screens = getattr(
            proposal,
            "screen_list",
            None,
        )

    if screens is None:
        screens = []

    # --------------------------------------------------------
    # 2. HANDLE DJANGO RELATED MANAGER / QUERYSET
    # --------------------------------------------------------
    #
    # Example:
    #
    #     proposal.screens
    #
    # may be a RelatedManager rather than an iterable list.
    #
    # Calling .all() converts it into a QuerySet that can safely
    # be iterated.
    # --------------------------------------------------------

    if hasattr(screens, "all") and callable(screens.all):
        try:
            screens = screens.all()
        except Exception:
            screens = []

    # --------------------------------------------------------
    # 3. HANDLE STRING VALUES
    # --------------------------------------------------------

    if isinstance(screens, str):
        screens = [
            line.strip()
            for line in screens.splitlines()
            if line.strip()
        ]

    # --------------------------------------------------------
    # 4. HANDLE A SINGLE DICTIONARY
    # --------------------------------------------------------

    if isinstance(screens, dict):
        screens = [screens]

    # --------------------------------------------------------
    # 5. MAKE SURE THE VALUE IS ITERABLE
    # --------------------------------------------------------

    try:
        screen_list = list(screens)
    except TypeError:
        screen_list = [screens] if screens else []

    result = []

    # --------------------------------------------------------
    # 6. NORMALIZE EACH SCREEN
    # --------------------------------------------------------

    for index, screen in enumerate(
        screen_list,
        start=1,
    ):

        name = ""
        description = ""
        purpose = ""

        # ====================================================
        # DICTIONARY SCREEN
        # ====================================================

        if isinstance(screen, dict):

            name = (
                screen.get("name")
                or screen.get("title")
                or screen.get("label")
                or screen.get("screen_name")
                or screen.get("page_name")
                or f"Screen {index}"
            )

            description = (
                screen.get("description")
                or screen.get("details")
                or screen.get("content")
                or screen.get("summary")
                or ""
            )

            purpose = (
                screen.get("purpose")
                or screen.get("function")
                or screen.get("objective")
                or ""
            )

        # ====================================================
        # DJANGO MODEL INSTANCE
        # ====================================================
        #
        # ProposalScreen objects fall here.
        # We intentionally use getattr() rather than depending
        # on one exact model definition.
        # ====================================================

        elif hasattr(screen, "_meta"):

            name = (
                getattr(screen, "name", None)
                or getattr(screen, "title", None)
                or getattr(screen, "label", None)
                or getattr(screen, "screen_name", None)
                or getattr(screen, "page_name", None)
                or f"Screen {index}"
            )

            description = (
                getattr(screen, "description", None)
                or getattr(screen, "details", None)
                or getattr(screen, "content", None)
                or getattr(screen, "summary", None)
                or ""
            )

            purpose = (
                getattr(screen, "purpose", None)
                or getattr(screen, "function", None)
                or getattr(screen, "objective", None)
                or ""
            )

        # ====================================================
        # SIMPLE STRING / OTHER VALUE
        # ====================================================

        else:

            name = str(screen).strip()

            if not name:
                name = f"Screen {index}"

        # ----------------------------------------------------
        # 7. CLEAN VALUES
        # ----------------------------------------------------

        name = str(
            name or f"Screen {index}"
        ).strip()

        description = str(
            description or ""
        ).strip()

        purpose = str(
            purpose or ""
        ).strip()

        # ----------------------------------------------------
        # 8. SKIP COMPLETELY EMPTY ENTRIES
        # ----------------------------------------------------

        if not (
            name
            or description
            or purpose
        ):
            continue

        # ----------------------------------------------------
        # 9. ADD NORMALIZED SCREEN
        # ----------------------------------------------------

        result.append(
            {
                "name": name,
                "description": description,
                "purpose": purpose,
            }
        )

    return result

def _add_section_title(
    story,
    title,
    heading_style,
):
    """
    Add a clean section heading with an accent line.
    """

    story.append(
        Spacer(1, 3 * mm)
    )

    heading_table = Table(
        [
            [
                Paragraph(
                    _safe_text(title),
                    heading_style,
                ),
                "",
            ]
        ],
        colWidths=[
            155 * mm,
            15 * mm,
        ],
    )

    heading_table.setStyle(
        TableStyle(
            [
                (
                    "LINEBELOW",
                    (0, 0),
                    (0, 0),
                    1.8,
                    ACCENT,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "BOTTOM",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(
        heading_table
    )

    story.append(
        Spacer(1, 3 * mm)
    )


# ============================================================
# PAGE HEADER / FOOTER
# ============================================================

def _draw_page(canvas, document):
    canvas.saveState()

    width, height = A4

    # Top accent line
    canvas.setFillColor(ACCENT)
    canvas.rect(
        0,
        height - 4,
        width,
        4,
        fill=1,
        stroke=0,
    )

    # Header
    canvas.setFont(
        "Helvetica-Bold",
        8,
    )

    canvas.setFillColor(PRIMARY)

    canvas.drawString(
        15 * mm,
        height - 10 * mm,
        "AB TECHNOLOGIES",
    )

    canvas.setFont(
        "Helvetica",
        7,
    )

    canvas.setFillColor(MUTED)

    canvas.drawRightString(
        width - 15 * mm,
        height - 10 * mm,
        "Technology. Simplified.",
    )

    # Footer line
    canvas.setStrokeColor(BORDER)

    canvas.line(
        15 * mm,
        12 * mm,
        width - 15 * mm,
        12 * mm,
    )

    # Footer text
    canvas.setFont(
        "Helvetica",
        7,
    )

    canvas.setFillColor(MUTED)

    canvas.drawString(
        15 * mm,
        7 * mm,
        "AB Technologies",
    )

    canvas.drawCentredString(
        width / 2,
        7 * mm,
        "Technology. Simplified.",
    )

    canvas.drawRightString(
        width - 15 * mm,
        7 * mm,
        f"Page {document.page}",
    )

    canvas.restoreState()


# ============================================================
# MAIN PDF GENERATOR
# ============================================================

def generate_proposal_pdf(proposal):
    """
    Generate a polished client-facing AB Technologies proposal PDF.

    Supports:

    SOFTWARE / SERVICE PROPOSALS
        - Client information
        - Project summary
        - Objectives
        - Screens/interfaces
        - Accepted scope
        - Investment
        - Acceptance information

    PROCUREMENT QUOTATIONS
        - Client information
        - Request summary
        - Purpose
        - Quotation items
        - Brand/model
        - Quantity
        - Unit price
        - Line total
        - Discount
        - Tax
        - Delivery
        - Final quotation total
        - Acceptance information

    The PDF is generated entirely in memory.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=(
            getattr(
                proposal,
                "title",
                None,
            )
            or "AB Technologies Proposal"
        ),
        author="AB Technologies",
        subject=(
            getattr(
                proposal,
                "title",
                None,
            )
            or "Proposal"
        ),
    )

    # ========================================================
    # STYLES
    # ========================================================

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ProposalTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=27,
        alignment=TA_CENTER,
        textColor=PRIMARY,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        "ProposalSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=MUTED,
        spaceAfter=7,
    )

    project_title_style = ParagraphStyle(
        "ProjectTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=23,
        alignment=TA_CENTER,
        textColor=PRIMARY,
        spaceBefore=3,
        spaceAfter=8,
    )

    document_type_style = ParagraphStyle(
        "DocumentType",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=ACCENT,
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "ProposalHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=PRIMARY,
        spaceBefore=0,
        spaceAfter=5,
    )

    subheading_style = ParagraphStyle(
        "ProposalSubHeading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=PRIMARY,
        spaceAfter=3,
    )

    normal_style = ParagraphStyle(
        "ProposalNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=SECONDARY,
        spaceAfter=3,
    )

    small_style = ParagraphStyle(
        "ProposalSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    )

    bullet_style = ParagraphStyle(
        "ProposalBullet",
        parent=normal_style,
        leftIndent=7 * mm,
        firstLineIndent=-4 * mm,
        spaceAfter=2,
    )

    feature_name_style = ParagraphStyle(
        "FeatureName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=PRIMARY,
    )

    feature_description_style = ParagraphStyle(
        "FeatureDescription",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=SECONDARY,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=WHITE,
    )

    quotation_product_style = ParagraphStyle(
        "QuotationProduct",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=PRIMARY,
    )

    quotation_meta_style = ParagraphStyle(
        "QuotationMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=MUTED,
    )

    price_style = ParagraphStyle(
        "ProposalPrice",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=TA_RIGHT,
        textColor=PRIMARY,
    )

    total_label_style = ParagraphStyle(
        "ProposalTotalLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=PRIMARY,
    )

    total_price_style = ParagraphStyle(
        "ProposalTotalPrice",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        alignment=TA_RIGHT,
        textColor=ACCENT,
    )

    # ========================================================
    # STORY
    # ========================================================

    story = []

    # ========================================================
    # DETERMINE DOCUMENT TYPE
    # ========================================================

    quotation = _get_quotation_from_proposal(
        proposal
    )

    is_quotation = bool(
        quotation
    )

    if is_quotation:
        document_type = "PROCUREMENT QUOTATION"
    else:
        document_type = "SOFTWARE / TECHNOLOGY PROPOSAL"

    # ========================================================
    # COVER / HEADER
    # ========================================================

    story.append(
        Spacer(1, 5 * mm)
    )

    story.append(
        Paragraph(
            "AB TECHNOLOGIES",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "Technology. Simplified.",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            _safe_text(document_type),
            document_type_style,
        )
    )

    story.append(
        Paragraph(
            _safe_text(
                getattr(
                    proposal,
                    "title",
                    None,
                )
                or (
                    quotation.get("title")
                    if quotation
                    else "Technology Proposal"
                )
            ),
            project_title_style,
        )
    )

    # ========================================================
    # CLIENT INFORMATION CARD
    # ========================================================

    lead = getattr(
        proposal,
        "lead",
        None,
    )

    client_name = (
        getattr(
            lead,
            "name",
            "",
        )
        or ""
    ).strip()

    client_company = (
        getattr(
            lead,
            "company",
            "",
        )
        or ""
    ).strip()

    client_email = (
        getattr(
            lead,
            "email",
            "",
        )
        or ""
    ).strip()

    client_phone = (
        getattr(
            lead,
            "phone",
            "",
        )
        or ""
    ).strip()

    client_country = (
        getattr(
            lead,
            "country",
            "",
        )
        or ""
    ).strip()

    proposal_version = (
        getattr(
            proposal,
            "accepted_version",
            None,
        )
        or getattr(
            proposal,
            "version",
            1,
        )
    )

    client_rows = [
        [
            Paragraph(
                "<b>CLIENT</b>",
                small_style,
            ),
            Paragraph(
                _safe_text(
                    client_name
                    or "N/A"
                ),
                normal_style,
            ),
            Paragraph(
                "<b>VERSION</b>",
                small_style,
            ),
            Paragraph(
                _safe_text(
                    proposal_version
                ),
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>COMPANY</b>",
                small_style,
            ),
            Paragraph(
                _safe_text(
                    client_company
                    or "N/A"
                ),
                normal_style,
            ),
            Paragraph(
                "<b>COUNTRY</b>",
                small_style,
            ),
            Paragraph(
                _safe_text(
                    client_country
                    or "N/A"
                ),
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>EMAIL</b>",
                small_style,
            ),
            Paragraph(
                _safe_text(
                    client_email
                    or "N/A"
                ),
                normal_style,
            ),
            Paragraph(
                "<b>PHONE</b>",
                small_style,
            ),
            Paragraph(
                _safe_text(
                    client_phone
                    or "N/A"
                ),
                normal_style,
            ),
        ],
    ]

    client_table = Table(
        client_rows,
        colWidths=[
            22 * mm,
            68 * mm,
            22 * mm,
            58 * mm,
        ],
    )

    client_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    LIGHT,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    BORDER,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    LIGHTER,
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    LIGHTER,
                ),
            ]
        )
    )

    story.append(
        client_table
    )

    story.append(
        Spacer(1, 8 * mm)
    )

    # ========================================================
    # PROCUREMENT QUOTATION
    # ========================================================

    if is_quotation:

        currency = (
            quotation.get("currency")
            or "NGN"
        )

        # ----------------------------------------------------
        # QUOTATION SUMMARY
        # ----------------------------------------------------

        _add_section_title(
            story,
            "Quotation Summary",
            heading_style,
        )

        description = (
            quotation.get(
                "description"
            )
            or ""
        )

        purpose = (
            quotation.get(
                "purpose"
            )
            or ""
        )

        request_type = (
            quotation.get(
                "request_type"
            )
            or "procurement"
        )

        summary_rows = [
            [
                Paragraph(
                    "<b>Request Type</b>",
                    normal_style,
                ),
                Paragraph(
                    _safe_text(
                        request_type.title()
                    ),
                    normal_style,
                ),
            ],
        ]

        if description:
            summary_rows.append(
                [
                    Paragraph(
                        "<b>Request</b>",
                        normal_style,
                    ),
                    Paragraph(
                        _safe_text(
                            description
                        ),
                        normal_style,
                    ),
                ]
            )

        if purpose:
            summary_rows.append(
                [
                    Paragraph(
                        "<b>Purpose</b>",
                        normal_style,
                    ),
                    Paragraph(
                        _safe_text(
                            purpose
                        ),
                        normal_style,
                    ),
                ]
            )

        summary_table = Table(
            summary_rows,
            colWidths=[
                38 * mm,
                132 * mm,
            ],
        )

        summary_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, -1),
                        LIGHTER,
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.6,
                        BORDER,
                    ),
                    (
                        "INNERGRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        BORDER,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                ]
            )
        )

        story.append(
            summary_table
        )

        story.append(
            Spacer(1, 7 * mm)
        )

        # ----------------------------------------------------
        # QUOTATION ITEMS
        # ----------------------------------------------------

        _add_section_title(
            story,
            "Quotation Items",
            heading_style,
        )

        quotation_items = (
            quotation.get("items")
            or []
        )

        quotation_rows = [
            [
                Paragraph(
                    "<b>#</b>",
                    table_header_style,
                ),
                Paragraph(
                    "<b>PRODUCT / ITEM</b>",
                    table_header_style,
                ),
                Paragraph(
                    "<b>BRAND / MODEL</b>",
                    table_header_style,
                ),
                Paragraph(
                    "<b>QTY</b>",
                    table_header_style,
                ),
                Paragraph(
                    "<b>UNIT PRICE</b>",
                    table_header_style,
                ),
                Paragraph(
                    "<b>TOTAL</b>",
                    table_header_style,
                ),
            ]
        ]

        selected_count = 0

        for index, item in enumerate(
            quotation_items,
            start=1,
        ):

            # Accepted snapshots should already contain
            # only included products. But respect "included"
            # if it exists for safety.
            if (
                "included" in item
                and not item.get(
                    "included",
                    True,
                )
            ):
                continue

            selected_count += 1

            name = (
                item.get("name")
                or "Item"
            )

            brand = (
                item.get("brand")
                or ""
            )

            model = (
                item.get("model")
                or ""
            )

            brand_model = " ".join(
                part
                for part in [
                    brand,
                    model,
                ]
                if part
            )

            quantity = item.get(
                "quantity"
            ) or 0

            unit_price = item.get(
                "unit_price"
            )

            total_price = item.get(
                "total_price"
            )

            description = (
                item.get(
                    "description"
                )
                or ""
            )

            product_text = Paragraph(
                (
                    f"<b>{_safe_text(name)}</b>"
                    + (
                        f"<br/><font size='7' color='#6B7280'>"
                        f"{_safe_text(description)}</font>"
                        if description
                        else ""
                    )
                ),
                quotation_product_style,
            )

            brand_model_text = Paragraph(
                _safe_text(
                    brand_model
                    or "—"
                ),
                quotation_meta_style,
            )

            quotation_rows.append(
                [
                    Paragraph(
                        str(selected_count),
                        quotation_meta_style,
                    ),
                    product_text,
                    brand_model_text,
                    Paragraph(
                        str(quantity),
                        price_style,
                    ),
                    Paragraph(
                        _safe_text(
                            _format_money(
                                unit_price,
                                currency,
                            )
                        )
                        if unit_price
                        is not None
                        else "—",
                        price_style,
                    ),
                    Paragraph(
                        _safe_text(
                            _format_money(
                                total_price,
                                currency,
                            )
                        )
                        if total_price
                        is not None
                        else "—",
                        price_style,
                    ),
                ]
            )

        if len(quotation_rows) == 1:
            quotation_rows.append(
                [
                    "",
                    Paragraph(
                        "No quotation items were recorded.",
                        normal_style,
                    ),
                    "",
                    "",
                    "",
                    "",
                ]
            )

        quotation_table = Table(
            quotation_rows,
            colWidths=[
                8 * mm,
                55 * mm,
                34 * mm,
                13 * mm,
                30 * mm,
                30 * mm,
            ],
            repeatRows=1,
        )

        quotation_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        PRIMARY,
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.6,
                        BORDER,
                    ),
                    (
                        "INNERGRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        BORDER,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "ALIGN",
                        (0, 1),
                        (0, -1),
                        "CENTER",
                    ),
                    (
                        "ALIGN",
                        (3, 1),
                        (5, -1),
                        "RIGHT",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        6,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        6,
                    ),
                ]
            )
        )

        # Alternating rows
        for row_index in range(
            1,
            len(quotation_rows),
        ):
            if row_index % 2 == 0:
                quotation_table.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, row_index),
                                (-1, row_index),
                                LIGHT,
                            )
                        ]
                    )
                )

        story.append(
            quotation_table
        )

        story.append(
            Spacer(1, 7 * mm)
        )

        # ----------------------------------------------------
        # QUOTATION FINANCIAL SUMMARY
        # ----------------------------------------------------

        _add_section_title(
            story,
            "Quotation Summary",
            heading_style,
        )

        subtotal = quotation.get(
            "subtotal"
        ) or "0"

        discount = quotation.get(
            "discount"
        ) or "0"

        tax = quotation.get(
            "tax"
        ) or "0"

        delivery_fee = quotation.get(
            "delivery_fee"
        ) or "0"

        total = quotation.get(
            "total"
        ) or "0"

        financial_rows = [
            [
                Paragraph(
                    "Subtotal",
                    normal_style,
                ),
                Paragraph(
                    _safe_text(
                        _format_money(
                            subtotal,
                            currency,
                        )
                    ),
                    price_style,
                ),
            ],
            [
                Paragraph(
                    "Discount",
                    normal_style,
                ),
                Paragraph(
                    _safe_text(
                        _format_money(
                            discount,
                            currency,
                        )
                    ),
                    price_style,
                ),
            ],
            [
                Paragraph(
                    "Tax",
                    normal_style,
                ),
                Paragraph(
                    _safe_text(
                        _format_money(
                            tax,
                            currency,
                        )
                    ),
                    price_style,
                ),
            ],
            [
                Paragraph(
                    "Delivery / Logistics",
                    normal_style,
                ),
                Paragraph(
                    _safe_text(
                        _format_money(
                            delivery_fee,
                            currency,
                        )
                    ),
                    price_style,
                ),
            ],
            [
                Paragraph(
                    "<b>FINAL QUOTATION TOTAL</b>",
                    total_label_style,
                ),
                Paragraph(
                    f"<b>{_safe_text(_format_money(total, currency))}</b>",
                    total_price_style,
                ),
            ],
        ]

        financial_table = Table(
            financial_rows,
            colWidths=[
                110 * mm,
                60 * mm,
            ],
        )

        financial_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -2),
                        LIGHT,
                    ),
                    (
                        "BACKGROUND",
                        (0, -1),
                        (-1, -1),
                        ACCENT_LIGHT,
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.7,
                        BORDER,
                    ),
                    (
                        "LINEABOVE",
                        (0, -1),
                        (-1, -1),
                        1.2,
                        ACCENT,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        9,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        9,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                ]
            )
        )

        story.append(
            financial_table
        )

        story.append(
            Spacer(1, 7 * mm)
        )

        notes = quotation.get(
            "notes"
        )

        if notes:
            _add_section_title(
                story,
                "Quotation Notes",
                heading_style,
            )

            notes_box = Table(
                [
                    [
                        Paragraph(
                            _safe_text(
                                notes
                            ),
                            normal_style,
                        )
                    ]
                ],
                colWidths=[
                    170 * mm
                ],
            )

            notes_box.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, -1),
                            LIGHT,
                        ),
                        (
                            "BOX",
                            (0, 0),
                            (-1, -1),
                            0.6,
                            BORDER,
                        ),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            9,
                        ),
                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            9,
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            8,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            8,
                        ),
                    ]
                )
            )

            story.append(
                notes_box
            )

    # ========================================================
    # SOFTWARE / SERVICE PROPOSAL
    # ========================================================

    else:

        # ----------------------------------------------------
        # PROJECT SUMMARY
        # ----------------------------------------------------

        summary = (
            getattr(
                proposal,
                "summary",
                None,
            )
            or getattr(
                proposal,
                "project_summary",
                None,
            )
            or ""
        )

        if not summary:
            summary = (
                getattr(
                    proposal,
                    "project_request",
                    None,
                )
                or ""
            )

        summary_text = str(
            summary
        ).strip()

        if summary_text:

            _add_section_title(
                story,
                "Project Summary",
                heading_style,
            )

            summary_box = Table(
                [
                    [
                        Paragraph(
                            _safe_text(
                                summary_text
                            ),
                            normal_style,
                        )
                    ]
                ],
                colWidths=[
                    170 * mm
                ],
            )

            summary_box.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, -1),
                            LIGHT,
                        ),
                        (
                            "BOX",
                            (0, 0),
                            (-1, -1),
                            0.6,
                            BORDER,
                        ),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            9,
                        ),
                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            9,
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            8,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            8,
                        ),
                    ]
                )
            )

            story.append(
                summary_box
            )

        # ----------------------------------------------------
        # OBJECTIVES
        # ----------------------------------------------------

        objectives = (
            getattr(
                proposal,
                "objectives",
                None,
            )
            or getattr(
                proposal,
                "project_objectives",
                None,
            )
            or []
        )

        objective_items = _normalise_list(
            objectives
        )

        if objective_items:

            _add_section_title(
                story,
                "Project Objectives",
                heading_style,
            )

            _add_bullet_list(
                story,
                objective_items,
                normal_style,
                bullet_style,
            )

        # ----------------------------------------------------
        # SCREENS
        # ----------------------------------------------------

        screen_items = _get_screen_items(
            proposal
        )

        if screen_items:

            _add_section_title(
                story,
                "Screens & Interfaces",
                heading_style,
            )

            screen_rows = [
                [
                    Paragraph(
                        "<b>SCREEN / INTERFACE</b>",
                        table_header_style,
                    ),
                    Paragraph(
                        "<b>DESCRIPTION</b>",
                        table_header_style,
                    ),
                    Paragraph(
                        "<b>PURPOSE</b>",
                        table_header_style,
                    ),
                ]
            ]

            for screen in screen_items:

                screen_rows.append(
                    [
                        Paragraph(
                            _safe_text(
                                screen["name"]
                            ),
                            feature_name_style,
                        ),
                        Paragraph(
                            _safe_text(
                                screen["description"]
                                or "—"
                            ),
                            feature_description_style,
                        ),
                        Paragraph(
                            _safe_text(
                                screen["purpose"]
                                or "—"
                            ),
                            feature_description_style,
                        ),
                    ]
                )

            screens_table = Table(
                screen_rows,
                colWidths=[
                    48 * mm,
                    70 * mm,
                    52 * mm,
                ],
                repeatRows=1,
            )

            screens_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            PRIMARY,
                        ),
                        (
                            "BOX",
                            (0, 0),
                            (-1, -1),
                            0.6,
                            BORDER,
                        ),
                        (
                            "INNERGRID",
                            (0, 0),
                            (-1, -1),
                            0.25,
                            BORDER,
                        ),
                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "TOP",
                        ),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            6,
                        ),
                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            6,
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            6,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            6,
                        ),
                    ]
                )
            )

            for row_index in range(
                1,
                len(screen_rows),
            ):
                if row_index % 2 == 0:
                    screens_table.setStyle(
                        TableStyle(
                            [
                                (
                                    "BACKGROUND",
                                    (0, row_index),
                                    (-1, row_index),
                                    LIGHT,
                                )
                            ]
                        )
                    )

            story.append(
                screens_table
            )

        # ----------------------------------------------------
        # ACCEPTED PROJECT SCOPE
        # ----------------------------------------------------

        _add_section_title(
            story,
            "Accepted Project Scope",
            heading_style,
        )

        features = (
            proposal.proposal_features
            .filter(
                status="approved",
                scope_status__in={
                    "required",
                    "recommended",
                },
            )
            .order_by(
                "sort_order",
                "id",
            )
        )

        feature_rows = [
            [
                Paragraph(
                    "<b>FEATURE</b>",
                    table_header_style,
                ),
                Paragraph(
                    "<b>DESCRIPTION</b>",
                    table_header_style,
                ),
            ]
        ]

        for feature in features:

            feature_rows.append(
                [
                    Paragraph(
                        _safe_text(
                            feature.name
                            or ""
                        ),
                        feature_name_style,
                    ),
                    Paragraph(
                        _safe_text(
                            feature.description
                            or ""
                        ),
                        feature_description_style,
                    ),
                ]
            )

        if len(feature_rows) > 1:

            feature_table = Table(
                feature_rows,
                colWidths=[
                    50 * mm,
                    120 * mm,
                ],
                repeatRows=1,
            )

            feature_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            PRIMARY,
                        ),
                        (
                            "BOX",
                            (0, 0),
                            (-1, -1),
                            0.6,
                            BORDER,
                        ),
                        (
                            "INNERGRID",
                            (0, 0),
                            (-1, -1),
                            0.25,
                            BORDER,
                        ),
                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "TOP",
                        ),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            7,
                        ),
                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            7,
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            7,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            7,
                        ),
                    ]
                )
            )

            story.append(
                feature_table
            )

        else:

            story.append(
                Paragraph(
                    "No project features were recorded.",
                    small_style,
                )
            )

        # ----------------------------------------------------
        # PROJECT INVESTMENT
        # ----------------------------------------------------

        currency = (
            getattr(
                proposal,
                "currency",
                None,
            )
            or "NGN"
        )

        total = getattr(
            proposal,
            "total_price",
            None,
        )

        _add_section_title(
            story,
            "Project Investment",
            heading_style,
        )

        total_table = Table(
            [
                [
                    Paragraph(
                        "<b>Accepted Project Investment</b>",
                        total_label_style,
                    ),
                    Paragraph(
                        f"<b>{_safe_text(_format_money(total, currency))}</b>",
                        total_price_style,
                    ),
                ]
            ],
            colWidths=[
                110 * mm,
                60 * mm,
            ],
        )

        total_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        ACCENT_LIGHT,
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.8,
                        ACCENT,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        10,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        10,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        11,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        11,
                    ),
                ]
            )
        )

        story.append(
            total_table
        )

    # ========================================================
    # ACCEPTANCE INFORMATION
    # ========================================================

    story.append(
        Spacer(1, 8 * mm)
    )

    _add_section_title(
        story,
        "Acceptance Information",
        heading_style,
    )

    accepted_at = (
        proposal.accepted_at.strftime(
            "%B %d, %Y at %I:%M %p"
        )
        if getattr(
            proposal,
            "accepted_at",
            None,
        )
        else "N/A"
    )

    acceptance_rows = [
        [
            Paragraph(
                "<b>Status</b>",
                normal_style,
            ),
            Paragraph(
                "Accepted",
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>Accepted Version</b>",
                normal_style,
            ),
            Paragraph(
                _safe_text(
                    getattr(
                        proposal,
                        "accepted_version",
                        None,
                    )
                    or getattr(
                        proposal,
                        "version",
                        1,
                    )
                ),
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>Accepted At</b>",
                normal_style,
            ),
            Paragraph(
                _safe_text(
                    accepted_at
                ),
                normal_style,
            ),
        ],
    ]

    acceptance_table = Table(
        acceptance_rows,
        colWidths=[
            45 * mm,
            125 * mm,
        ],
    )

    acceptance_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    SUCCESS_LIGHT,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    BORDER,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(
        acceptance_table
    )

    # ========================================================
    # FINAL MESSAGE
    # ========================================================

    story.append(
        Spacer(1, 12 * mm)
    )

    closing_box = Table(
        [
            [
                Paragraph(
                    "<b>Thank you for choosing AB Technologies.</b>",
                    normal_style,
                )
            ],
            [
                Paragraph(
                    (
                        "This document represents the scope, "
                        "quotation or project investment accepted "
                        "by the client."
                    ),
                    small_style,
                )
            ],
            [
                Paragraph(
                    (
                        "Any changes to the accepted scope may "
                        "require a revised proposal and additional "
                        "approval."
                    ),
                    small_style,
                )
            ],
        ],
        colWidths=[
            170 * mm
        ],
    )

    closing_box.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    LIGHT,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    BORDER,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    story.append(
        closing_box
    )

    # ========================================================
    # BUILD
    # ========================================================

    document.build(
        story,
        onFirstPage=_draw_page,
        onLaterPages=_draw_page,
    )

    buffer.seek(0)

    return buffer