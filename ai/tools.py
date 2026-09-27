from decimal import Decimal, InvalidOperation
import logging

from django.core.exceptions import ValidationError
from django.db import DataError, IntegrityError, transaction

from crm.models import (
    Lead,
    QuoteRequest,
    ProcurementQuotationItem,
    ProjectRequest,
    SupportTicket,
)


logger = logging.getLogger(__name__)


VALID_LEAD_INTENTS = {
    "general",
    "service",
    "procurement",
    "product",
    "training",
    "support",
    "consultation",
    "project",
    "other",
}

VALID_LEAD_STATUSES = {
    "new",
    "contacted",
    "qualified",
    "converted",
    "lost",
}

VALID_SUPPORT_PRIORITIES = {
    "low",
    "normal",
    "high",
    "urgent",
}


def _clean_text(value, max_length=None):
    """Normalize arbitrary AI/tool text before saving it."""
    value = str(value or "").strip()
    if max_length is not None:
        value = value[:max_length]
    return value


def normalize_lead_intent(intent):
    """Map AI-generated intent text to a valid Lead intent choice."""
    value = _clean_text(intent).lower()

    if value in VALID_LEAD_INTENTS:
        return value

    if any(word in value for word in (
        "procurement", "procure", "purchase", "purchasing", "buy",
        "hardware", "equipment", "laptop", "computer", "server",
        "printer", "device", "cctv", "camera", "router", "switch",
    )):
        return "procurement"

    if any(word in value for word in (
        "support", "technical issue", "technical problem",
        "troubleshoot", "repair", "fix", "maintenance",
    )):
        return "support"

    if any(word in value for word in (
        "training", "course", "learn", "learning",
        "certification", "workshop",
    )):
        return "training"

    if any(word in value for word in (
        "consultation", "consulting", "consult", "advisory", "advice",
    )):
        return "consultation"

    if any(word in value for word in (
        "project", "implementation", "deployment", "rollout",
    )):
        return "project"

    if any(word in value for word in (
        "product", "subscription", "license", "licence",
    )):
        return "product"

    if any(word in value for word in (
        "service", "software", "website", "web development",
        "application", "app development", "cloud", "networking",
        "cybersecurity", "automation", "managed it",
    )):
        return "service"

    return "other" if value else "general"


def normalize_lead_status(status):
    """Map AI-generated status text to a valid Lead status choice."""
    value = _clean_text(status).lower()

    if value in VALID_LEAD_STATUSES:
        return value

    aliases = {
        "new lead": "new",
        "pending": "new",
        "open": "new",
        "reached": "contacted",
        "reached out": "contacted",
        "in contact": "contacted",
        "interested": "qualified",
        "qualified lead": "qualified",
        "customer": "converted",
        "won": "converted",
        "closed won": "converted",
        "not interested": "lost",
        "closed lost": "lost",
    }
    return aliases.get(value, "new")


def normalize_support_priority(priority):
    """Map AI-generated priority text to a valid SupportTicket choice."""
    value = _clean_text(priority).lower()

    if value in VALID_SUPPORT_PRIORITIES:
        return value

    if any(word in value for word in ("critical", "emergency", "immediate")):
        return "urgent"
    if any(word in value for word in ("important", "serious", "high priority")):
        return "high"
    if any(word in value for word in ("minor", "low priority")):
        return "low"

    return "normal"


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

    normalized_intent = normalize_lead_intent(intent)

    try:
        lead = Lead.objects.create(
            name=_clean_text(name, 255),
            email=_clean_text(email, 254),
            phone=_clean_text(phone, 50),
            company=_clean_text(company, 255),
            intent=normalized_intent,
            notes=_clean_text(notes),
            source="ai",
            conversation=conversation,
        )
    except (DataError, IntegrityError) as exc:
        logger.exception("Failed to create CRM lead.")
        return {
            "success": False,
            "error": "Unable to create lead because the supplied data was invalid.",
            "details": str(exc),
        }

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
        lead.name = _clean_text(name, 255)

    if email is not None:
        lead.email = _clean_text(email, 254)

    if phone is not None:
        lead.phone = _clean_text(phone, 50)

    if company is not None:
        lead.company = _clean_text(company, 255)

    if intent is not None:
        lead.intent = normalize_lead_intent(intent)

    if status is not None:
        lead.status = normalize_lead_status(status)

    if notes is not None:
        lead.notes = _clean_text(notes)

    try:
        lead.save()
    except (DataError, IntegrityError) as exc:
        logger.exception("Failed to update CRM lead %s.", lead_id)
        return {
            "success": False,
            "error": "Unable to update lead because the supplied data was invalid.",
            "details": str(exc),
        }

    return {
        "success": True,
        "lead_id": str(lead.id),
        "message": "Lead updated successfully.",
    }



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

    quote_fields = {
        "lead": lead,
        "title": _clean_text(title, 255),
        "description": description,
        "purpose": purpose,
        "notes": notes,
        "currency": _clean_text(currency, 10) or "NGN",
        "status": "draft",
    }

    # The current QuoteRequest model includes these fields. Keeping the
    # checks makes this tool tolerant of an older deployment during rollout.
    model_fields = {field.name for field in QuoteRequest._meta.get_fields()}

    if "request_type" in model_fields:
        valid_types = {"procurement", "service", "product", "mixed", "other"}
        normalized_type = _clean_text(request_type).lower()
        quote_fields["request_type"] = (
            normalized_type if normalized_type in valid_types else "other"
        )

    if "budget" in model_fields:
        quote_fields["budget"] = _to_decimal(budget)

    if "deadline" in model_fields:
        quote_fields["deadline"] = deadline or None

    quotation = QuoteRequest.objects.create(**quote_fields)

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
            category=_clean_text(category, 100),
            name=_clean_text(name, 255),
            brand=_clean_text(brand, 100) or None,
            model=_clean_text(model, 255) or None,
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
        title=_clean_text(title, 255),
        description=_clean_text(description),
        project_type=_clean_text(project_type, 100),
        budget=_to_decimal(budget),
        currency=_clean_text(currency, 10) or "USD",
        deadline=deadline,
        notes=_clean_text(notes),
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
        subject=_clean_text(subject, 255),
        description=_clean_text(description),
        priority=normalize_support_priority(priority),
    )

    return {
        "success": True,
        "ticket_id": str(ticket.id),
        "message": "Support ticket created successfully.",
    }