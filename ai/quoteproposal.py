# ai/quote_proposal.py

from decimal import Decimal

from django.db import transaction

from crm.models import QuoteRequest
from proposals.models import Proposal, ProposalRevision


# ============================================================
# HELPERS
# ============================================================

def decimal_string(value):
    if value is None:
        return "0.00"

    return str(
        Decimal(str(value)).quantize(
            Decimal("0.01")
        )
    )


# ============================================================
# VALIDATE QUOTE
# ============================================================

def validate_quote_for_proposal(quote):
    """
    A quotation can only become a proposal after pricing
    has been completed.

    Django is the authority here.
    """

    if quote.status != "priced":
        raise ValueError(
            "The quotation must be fully priced before "
            "a proposal can be generated."
        )

    items = list(
        quote.items.all()
    )

    if not items:
        raise ValueError(
            "The quotation does not contain any items."
        )

    unpriced_items = [
        item.name
        for item in items
        if item.unit_price is None
    ]

    if unpriced_items:
        raise ValueError(
            "The following quotation items are not priced: "
            + ", ".join(unpriced_items)
        )

    return items


# ============================================================
# BUILD AUTHORITATIVE QUOTE CONTEXT
# ============================================================

def build_quote_proposal_context(quote):
    """
    Build the data Gemini is allowed to use.

    IMPORTANT:

    Financial information comes directly from Django.

    Gemini does NOT calculate this information.
    """

    items = validate_quote_for_proposal(
        quote
    )

    lead = quote.lead

    return {
        "client": {
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "country": lead.country,
        },

        "quotation": {
            "id": str(quote.id),

            "title": quote.title,

            "request_type": (
                quote.request_type
            ),

            "description": (
                quote.description
            ),

            "purpose": quote.purpose,

            "notes": quote.notes,

            "budget": (
                decimal_string(
                    quote.budget
                )
                if quote.budget is not None
                else None
            ),

            "currency": quote.currency,

            "deadline": (
                quote.deadline.isoformat()
                if quote.deadline
                else None
            ),

            "subtotal": decimal_string(
                quote.subtotal
            ),

            "discount": decimal_string(
                quote.discount
            ),

            "tax": decimal_string(
                quote.tax
            ),

            "delivery_fee": decimal_string(
                quote.delivery_fee
            ),

            "total": decimal_string(
                quote.total
            ),
        },

        "items": [
            {
                "category": item.category,

                "name": item.name,

                "brand": item.brand,

                "model": item.model,

                "description": item.description,

                "specifications": (
                    item.specifications
                    or {}
                ),

                "quantity": item.quantity,

                "unit_price": decimal_string(
                    item.unit_price
                ),

                "total_price": decimal_string(
                    item.total_price
                ),
            }

            for item in items
        ],
    }


# ============================================================
# GEMINI PROPOSAL PROMPT
# ============================================================

def build_quote_proposal_prompt(context):
    """
    Prompt specifically for generating a professional
    procurement/service proposal from a priced quote.
    """

    return f"""
You are the proposal-writing AI for AB Technologies.

Generate a professional client-facing proposal from the
authoritative quotation data below.

AB Technologies provides technology procurement, software
development, infrastructure, cloud, cybersecurity,
automation, consulting and other technology services.

============================================================
CRITICAL FINANCIAL RULES
============================================================

The quotation data comes from Django and is authoritative.

NEVER:

- change a quantity
- change a brand
- change a model
- invent a brand
- invent a model
- invent specifications
- change a unit price
- calculate a different total
- change subtotal
- change discount
- change tax
- change delivery fee
- change currency
- add products
- remove quoted products

Do NOT calculate financial values.

Use the supplied values exactly.

============================================================
COMMERCIAL RULES
============================================================

Do not invent:

- warranty
- payment terms
- delivery commitments
- return policies
- installation commitments
- support commitments
- service-level agreements
- guarantees

unless they are explicitly present in the quotation data.

If something is not supplied, do not claim it.

============================================================
PROPOSAL RULES
============================================================

Create professional proposal content.

The proposal should:

- clearly explain what the client requested
- clearly identify the quoted items/services
- explain the purpose where supplied
- summarize the proposed solution
- identify deliverables
- identify reasonable assumptions
- identify exclusions where appropriate
- provide a sensible timeline only when supported
- distinguish confirmed scope from recommendations
- maintain a professional AB Technologies tone

============================================================
OPTIONAL RECOMMENDATIONS
============================================================

You may recommend relevant improvements.

However:

- recommendations are NOT part of the quoted price
- recommendations must not modify the quotation
- recommendations must not be presented as confirmed scope
- do not invent expensive or unrelated features

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Required structure:

{{
    "title": "",
    "executive_summary": "",
    "client_summary": "",

    "business_objectives": [],

    "confirmed_requirements": [],

    "recommended_requirements": [],

    "optional_future_features": [],

    "security": {{}},

    "recurring_costs": [],

    "scope": {{}},

    "pages": [],

    "features": [],

    "authentication": {{}},

    "integrations": [],

    "mobile": {{}},

    "backend": {{}},

    "devops": {{}},

    "technical_scope": {{}},

    "deliverables": [],

    "assumptions": [],

    "exclusions": [],

    "timeline": {{}},

    "ai_analysis": {{}}
}}

For procurement quotations, software-specific fields such as
pages, authentication, backend and mobile may remain empty.

============================================================
AUTHORITATIVE QUOTATION
============================================================

{context}
"""


# ============================================================
# PARSE GEMINI JSON
# ============================================================

def parse_proposal_response(response_text):
    """
    Safely convert Gemini's JSON response into a Python dict.
    """

    if not response_text:
        raise ValueError(
            "Gemini returned an empty proposal."
        )

    text = response_text.strip()

    # Remove accidental markdown fences.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        import json

        data = json.loads(text)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid proposal JSON."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "Gemini proposal response must be a JSON object."
        )

    return data


# ============================================================
# NORMALIZE GENERATED CONTENT
# ============================================================

def normalize_generated_proposal(data):
    """
    Make sure every Proposal JSON field has a safe value.
    """

    list_fields = [
        "business_objectives",
        "confirmed_requirements",
        "recommended_requirements",
        "optional_future_features",
        "recurring_costs",
        "pages",
        "features",
        "integrations",
        "deliverables",
        "assumptions",
        "exclusions",
    ]

    dict_fields = [
        "security",
        "scope",
        "authentication",
        "mobile",
        "backend",
        "devops",
        "technical_scope",
        "timeline",
        "ai_analysis",
    ]

    text_fields = [
        "title",
        "executive_summary",
        "client_summary",
    ]

    result = {}

    for field in text_fields:
        value = data.get(
            field,
            "",
        )

        if value is None:
            value = ""

        result[field] = str(
            value
        ).strip()

    for field in list_fields:
        value = data.get(
            field,
            [],
        )

        result[field] = (
            value
            if isinstance(value, list)
            else []
        )

    for field in dict_fields:
        value = data.get(
            field,
            {},
        )

        result[field] = (
            value
            if isinstance(value, dict)
            else {}
        )

    return result


# ============================================================
# BUILD PRICING SNAPSHOT
# ============================================================

def build_pricing_snapshot(quote):
    """
    Copy the exact financial state from Django.

    This is what protects us from Gemini changing money.
    """

    items = validate_quote_for_proposal(
        quote
    )

    return {
        "source": "quote_request",

        "quote_request_id": str(
            quote.id
        ),

        "currency": quote.currency,

        "items": [
            {
                "category": item.category,

                "name": item.name,

                "brand": item.brand,

                "model": item.model,

                "quantity": item.quantity,

                "unit_price": decimal_string(
                    item.unit_price
                ),

                "total_price": decimal_string(
                    item.total_price
                ),
            }

            for item in items
        ],

        "subtotal": decimal_string(
            quote.subtotal
        ),

        "discount": decimal_string(
            quote.discount
        ),

        "tax": decimal_string(
            quote.tax
        ),

        "delivery_fee": decimal_string(
            quote.delivery_fee
        ),

        "total": decimal_string(
            quote.total
        ),
    }


# ============================================================
# CREATE PROPOSAL
# ============================================================

@transaction.atomic
def create_proposal_from_quote(
    quote,
    generated,
    created_by=None,
):
    """
    Create the existing Proposal model.

    DO NOT create another proposal model.
    """

    items = validate_quote_for_proposal(
        quote
    )

    generated = normalize_generated_proposal(
        generated
    )

    pricing_snapshot = (
        build_pricing_snapshot(
            quote
        )
    )

    proposal = Proposal.objects.create(
        lead=quote.lead,

        quote_request=quote,

        source="quote_request",

        status="ready",

        title=(
            generated["title"]
            or quote.title
        ),

        executive_summary=(
            generated[
                "executive_summary"
            ]
        ),

        client_summary=(
            generated[
                "client_summary"
            ]
        ),

        business_objectives=(
            generated[
                "business_objectives"
            ]
        ),

        confirmed_requirements=(
            generated[
                "confirmed_requirements"
            ]
        ),

        recommended_requirements=(
            generated[
                "recommended_requirements"
            ]
        ),

        optional_future_features=(
            generated[
                "optional_future_features"
            ]
        ),

        security=generated[
            "security"
        ],

        recurring_costs=(
            generated[
                "recurring_costs"
            ]
        ),

        scope=generated[
            "scope"
        ],

        pages=generated[
            "pages"
        ],

        features=generated[
            "features"
        ],

        authentication=(
            generated[
                "authentication"
            ]
        ),

        integrations=(
            generated[
                "integrations"
            ]
        ),

        mobile=generated[
            "mobile"
        ],

        backend=generated[
            "backend"
        ],

        devops=generated[
            "devops"
        ],

        technical_scope=(
            generated[
                "technical_scope"
            ]
        ),

        deliverables=(
            generated[
                "deliverables"
            ]
        ),

        assumptions=(
            generated[
                "assumptions"
            ]
        ),

        exclusions=(
            generated[
                "exclusions"
            ]
        ),

        timeline=generated[
            "timeline"
        ],

        country=quote.lead.country,

        # ====================================================
        # DJANGO OWNS THESE
        # ====================================================

        currency=quote.currency,

        total_price=quote.total,

        pricing_snapshot=(
            pricing_snapshot
        ),

        ai_analysis=(
            generated[
                "ai_analysis"
            ]
        ),

        client_editable=True,

        version=1,

        created_by=created_by,
    )

    # ========================================================
    # CREATE INITIAL REVISION
    # ========================================================

    ProposalRevision.objects.create(
        proposal=proposal,

        version=1,

        source="ai",

        title=proposal.title,

        client_summary=(
            proposal.client_summary
        ),

        scope=proposal.scope,

        pages=proposal.pages,

        features=proposal.features,

        authentication=(
            proposal.authentication
        ),

        integrations=(
            proposal.integrations
        ),

        mobile=proposal.mobile,

        backend=proposal.backend,

        devops=proposal.devops,

        technical_scope=(
            proposal.technical_scope
        ),

        deliverables=(
            proposal.deliverables
        ),

        assumptions=(
            proposal.assumptions
        ),

        exclusions=(
            proposal.exclusions
        ),

        timeline=proposal.timeline,

        milestones=proposal.milestones,

        country=proposal.country,

        currency=proposal.currency,

        total_price=proposal.total_price,

        pricing_snapshot=(
            proposal.pricing_snapshot
        ),

        ai_analysis=proposal.ai_analysis,

        change_summary=(
            "Initial proposal generated "
            "from priced quotation."
        ),
    )

    return proposal






# ============================================================
# COMPLETE QUOTE → PROPOSAL WORKFLOW
# ============================================================

def generate_and_create_quote_proposal(
    quote_id,
    created_by=None,
):
    """
    Complete workflow:

        QuoteRequest
             ↓
        Validate priced
             ↓
        Gemini generates proposal content
             ↓
        Django creates Proposal
             ↓
        ProposalRevision v1
    """

    from .gemini import (
        generate_quote_proposal_content
    )

    quote = (
        QuoteRequest.objects
        .select_related("lead")
        .prefetch_related("items")
        .get(
            id=quote_id
        )
    )

    # --------------------------------------------------------
    # Make sure pricing is complete before Gemini is called.
    # --------------------------------------------------------

    validate_quote_for_proposal(
        quote
    )

    # --------------------------------------------------------
    # Gemini writes the proposal.
    # --------------------------------------------------------

    generated = (
        generate_quote_proposal_content(
            quote
        )
    )

    # --------------------------------------------------------
    # Django creates the actual Proposal.
    # --------------------------------------------------------

    proposal = create_proposal_from_quote(
        quote=quote,

        generated=generated,

        created_by=created_by,
    )

    return proposal