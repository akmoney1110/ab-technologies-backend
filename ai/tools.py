from crm.models import (
    Lead,
    QuoteRequest,
    ProjectRequest,
    SupportTicket,
)


def create_lead(
    *,
    name="",
    email="",
    phone="",
    company="",
    intent="general",
    notes="",
    source="AB AI",
    conversation=None,
):
    """
    Create a new CRM lead.
    """

    # ── AUTO-CAPTURE ENQUIRY FROM CONVERSATION ──
    if not notes and conversation:
        try:
            latest_user_msg = (
                conversation.message_set
                .filter(role="user")
                .order_by("-created_at")
                .first()
            )
            if latest_user_msg and latest_user_msg.content:
                notes = latest_user_msg.content[:2000]
        except Exception:
            pass

    lead = Lead.objects.create(
        name=name or "",
        email=email or "",
        phone=phone or "",
        company=company or "",
        intent=intent or "general",
        notes=notes or "",
        source="ai",
        conversation=conversation,
    )

    return {
        "success": True,
        "lead_id": str(lead.id),
        "message": "Lead created successfully.",
    }


def update_lead(
    lead_id,
    *,
    name=None,
    email=None,
    phone=None,
    company=None,
    intent=None,
    status=None,
    notes=None,
):
    """
    Update an existing lead.
    """

    try:
        lead = Lead.objects.get(id=lead_id)

    except Lead.DoesNotExist:
        return {
            "success": False,
            "error": "Lead not found.",
        }

    if name is not None:
        lead.name = name

    if email is not None:
        lead.email = email

    if phone is not None:
        lead.phone = phone

    if company is not None:
        lead.company = company

    if intent is not None:
        lead.intent = intent

    if status is not None:
        lead.status = status

    if notes is not None:
        lead.notes = notes

    lead.save()

    return {
        "success": True,
        "lead_id": str(lead.id),
        "message": "Lead updated successfully.",
    }

# ai/tools.py

from decimal import Decimal, InvalidOperation

from django.db import transaction

from crm.models import (
    Lead,
    QuoteRequest,
    ProcurementQuotationItem,
)


def _to_decimal(value):
    """
    Safely convert a value to Decimal.

    Returns None when the value is missing, empty, invalid,
    or explicitly null.
    """
    if value is None:
        return None

    if value == "":
        return None

    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return None


@transaction.atomic
def create_quote_request(
    lead_id,
    title,
    description="",
    request_type="other",
    purpose="",
    items=None,
    budget=None,
    currency=None,
    deadline=None,
    notes="",
):
    """
    Create a quotation request and its individual quotation items.

    Gemini extracts the client's requirements.

    Django is responsible for:
        - creating the QuoteRequest
        - creating ProcurementQuotationItem records
        - calculating item totals
        - calculating quotation subtotal
        - calculating quotation total
        - determining whether the quotation is priced

    IMPORTANT:
    request_type, budget and deadline are accepted because they are
    part of the Gemini tool contract.

    The current QuoteRequest model does not have dedicated database
    fields for them, so they are preserved in the notes field rather
    than causing a database error.
    """

    # ========================================================
    # VALIDATE LEAD
    # ========================================================

    if not lead_id:
        return {
            "success": False,
            "error": "A valid lead_id is required.",
        }

    try:
        lead = Lead.objects.get(
            id=lead_id
        )

    except Lead.DoesNotExist:
        return {
            "success": False,
            "error": "The specified lead does not exist.",
        }

    # ========================================================
    # NORMALIZE BASIC VALUES
    # ========================================================

    title = (
        str(title or "").strip()
    )

    description = (
        str(description or "").strip()
    )

    request_type = (
        str(request_type or "other").strip()
    )

    purpose = (
        str(purpose or "").strip()
    )

    notes = (
        str(notes or "").strip()
    )

    currency = (
        str(currency or "").strip().upper()
    )

    if not currency:
        currency = "NGN"

    # ========================================================
    # VALIDATE TITLE
    # ========================================================

    if not title:
        return {
            "success": False,
            "error": "A quotation title is required.",
        }

    # ========================================================
    # NORMALIZE ITEMS
    # ========================================================

    if items is None:
        items = []

    if not isinstance(items, list):
        return {
            "success": False,
            "error": "Quotation items must be an array.",
        }

    # ========================================================
    # BUILD EXTRA NOTES
    #
    # Current QuoteRequest does not have:
    #     request_type
    #     budget
    #     deadline
    #
    # Preserve them rather than silently throwing them away.
    # ========================================================

    extra_notes = []

    if request_type:
        extra_notes.append(
            f"Request type: {request_type}"
        )

    if budget is not None:
        extra_notes.append(
            f"Client budget: {budget}"
        )

    if deadline:
        extra_notes.append(
            f"Requested deadline: {deadline}"
        )

    if extra_notes:
        if notes:
            notes += "\n\n"

        notes += "\n".join(
            extra_notes
        )

    # ========================================================
    # CREATE QUOTATION
    # ========================================================

    quotation = QuoteRequest.objects.create(
        lead=lead,
        title=title,
        description=description,
        purpose=purpose,
        notes=notes,
        currency=currency,
        status="draft",
    )

    # ========================================================
    # CREATE ITEMS
    # ========================================================

    created_items = []

    for raw_item in items:

        if not isinstance(
            raw_item,
            dict,
        ):
            continue

        category = str(
            raw_item.get(
                "category",
                "",
            )
            or ""
        ).strip()

        name = str(
            raw_item.get(
                "name",
                "",
            )
            or ""
        ).strip()

        brand = raw_item.get(
            "brand"
        )

        model = raw_item.get(
            "model"
        )

        item_description = str(
            raw_item.get(
                "description",
                "",
            )
            or ""
        ).strip()

        specifications = raw_item.get(
            "specifications",
            {},
        )

        # ----------------------------------------------------
        # BRAND
        # ----------------------------------------------------

        if brand is not None:
            brand = str(
                brand
            ).strip()

        if not brand:
            brand = None

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        if model is not None:
            model = str(
                model
            ).strip()

        if not model:
            model = None

        # ----------------------------------------------------
        # SPECIFICATIONS
        # ----------------------------------------------------

        if not isinstance(
            specifications,
            dict,
        ):
            specifications = {}

        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        quantity = raw_item.get(
            "quantity",
            1,
        )

        try:
            quantity = int(
                quantity
            )
        except (
            TypeError,
            ValueError,
        ):
            quantity = 1

        if quantity < 1:
            quantity = 1

        # ----------------------------------------------------
        # PRICES
        # ----------------------------------------------------

        unit_price = _to_decimal(
            raw_item.get(
                "unit_price"
            )
        )

        client_total_price = _to_decimal(
            raw_item.get(
                "total_price"
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # If the client did not provide a price,
        # leave it NULL.
        #
        # Do NOT invent a price.
        # ----------------------------------------------------

        total_price = None

        if unit_price is not None:

            total_price = (
                Decimal(quantity)
                * unit_price
            )

        elif client_total_price is not None:

            # Only preserve an explicitly supplied total.
            total_price = client_total_price

        # ----------------------------------------------------
        # SKIP COMPLETELY EMPTY ITEMS
        # ----------------------------------------------------

        if not category and not name:
            continue

        if not category:
            category = "Other"

        if not name:
            name = category

        # ----------------------------------------------------
        # CREATE ITEM
        # ----------------------------------------------------

        item = ProcurementQuotationItem.objects.create(
            quotation=quotation,
            category=category,
            name=name,
            brand=brand,
            model=model,
            description=item_description,
            specifications=specifications,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

        created_items.append(
            item
        )

    # ========================================================
    # CALCULATE QUOTATION TOTALS
    # ========================================================

    subtotal = Decimal("0")

    for item in quotation.items.all():

        if item.unit_price is None:

            item.total_price = None

            item.save(
                update_fields=[
                    "total_price",
                    "updated_at",
                ]
            )

            continue

        item.total_price = (
            Decimal(item.quantity)
            * item.unit_price
        )

        item.save(
            update_fields=[
                "total_price",
                "updated_at",
            ]
        )

        subtotal += (
            item.total_price
            or Decimal("0")
        )

    quotation.subtotal = subtotal

    discount = (
        quotation.discount
        or Decimal("0")
    )

    tax = (
        quotation.tax
        or Decimal("0")
    )

    delivery_fee = (
        quotation.delivery_fee
        or Decimal("0")
    )

    quotation.total = (
        subtotal
        - discount
        + tax
        + delivery_fee
    )

    if quotation.total < Decimal("0"):
        quotation.total = Decimal("0")

    # ========================================================
    # DETERMINE STATUS
    # ========================================================

    all_items_priced = (
        quotation.items.exists()
        and not quotation.items.filter(
            unit_price__isnull=True
        ).exists()
    )

    if all_items_priced:
        quotation.status = "priced"
    else:
        quotation.status = "draft"

    quotation.save(
        update_fields=[
            "subtotal",
            "total",
            "status",
            "updated_at",
        ]
    )

    # ========================================================
    # RETURN RESULT TO GEMINI
    # ========================================================

    return {
        "success": True,

        "quote_request_id": str(
            quotation.id
        ),

        "lead_id": str(
            lead.id
        ),

        "title": quotation.title,

        "status": quotation.status,

        "request_type": request_type,

        "currency": quotation.currency,

        "item_count": quotation.items.count(),

        "items": [
            {
                "id": str(item.id),
                "category": item.category,
                "name": item.name,
                "brand": item.brand,
                "model": item.model,
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
            }
            for item in quotation.items.all()
        ],

        "subtotal": str(
            quotation.subtotal
        ),

        "total": str(
            quotation.total
        ),

        "message": (
            "Quotation request created successfully. "
            "The requested items have been recorded. "
            "Items without prices remain unpriced for "
            "AB Technologies staff to review."
        ),
    }


def create_project_request(
    *,
    lead_id,
    title,
    description="",
    project_type="",
    budget=None,
    currency="USD",
    deadline=None,
    notes="",
):
    """
    Create a project request.
    """

    try:
        lead = Lead.objects.get(id=lead_id)

    except Lead.DoesNotExist:
        return {
            "success": False,
        "error": "Lead not found.",
    }

    project = ProjectRequest.objects.create(
        lead=lead,
        title=title,
        description=description or "",
        project_type=project_type or "",
        budget=budget,
        currency=currency or "USD",
        deadline=deadline,
        notes=notes or "",
    )

    return {
        "success": True,
        "project_request_id": str(project.id),
        "message": "Project request created successfully.",
    }


def create_support_ticket(
    *,
    subject,
    description,
    lead_id=None,
    priority="normal",
):
    """
    Create a support ticket.
    """

    lead = None

    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)

        except Lead.DoesNotExist:
            return {
                "success": False,
                "error": "Lead not found.",
            }

    ticket = SupportTicket.objects.create(
        lead=lead,
        subject=subject,
        description=description,
        priority=priority or "normal",
    )

    return {
        "success": True,
        "ticket_id": str(ticket.id),
        "message": "Support ticket created successfully.",
    }