from django.db import transaction

from .models import Proposal, ProposalRevision
from .proposal_ai import generate_proposal_data

@transaction.atomic
def save_proposal_revision(
    proposal,
    data,
    source="ai",
    change_summary="",
):
    """
    Save a new proposal version.

    IMPORTANT:

    We NEVER overwrite the previous revision.

    Example:

        v1
        v2
        v3

    The Proposal itself always contains the latest version.
    """

    latest_revision = (
        proposal.revisions
        .order_by("-version")
        .first()
    )

    if latest_revision:
        next_version = latest_revision.version + 1
    else:
        next_version = 1

    # --------------------------------------------------------
    # Create immutable revision
    # --------------------------------------------------------

    revision = ProposalRevision.objects.create(
        proposal=proposal,
        version=next_version,
        source=source,

        title=data.get(
            "title",
            proposal.title,
        ),

        client_summary=data.get(
            "client_summary",
            "",
        ),

        scope=data.get(
            "scope",
            {},
        ),

        pages=data.get(
            "pages",
            [],
        ),

        features=data.get(
            "features",
            [],
        ),

        authentication=data.get(
            "authentication",
            {},
        ),

        integrations=data.get(
            "integrations",
            [],
        ),

        mobile=data.get(
            "mobile",
            {},
        ),

        backend=data.get(
            "backend",
            {},
        ),

        devops=data.get(
            "devops",
            {},
        ),

        technical_scope=data.get(
            "technical_scope",
            {},
        ),

        deliverables=data.get(
            "deliverables",
            [],
        ),

        assumptions=data.get(
            "assumptions",
            [],
        ),

        exclusions=data.get(
            "exclusions",
            [],
        ),

        timeline=data.get(
            "timeline",
            {},
        ),

        milestones=data.get(
            "milestones",
            [],
        ),

        country=data.get(
            "country",
            proposal.country,
        ),

        currency=data.get(
            "currency",
            proposal.currency,
        ),

        total_price=data.get(
            "total_price",
            proposal.total_price,
        ),

        pricing_snapshot=data.get(
            "pricing_snapshot",
            {},
        ),

        ai_analysis=data.get(
            "ai_analysis",
            {},
        ),

        change_summary=change_summary,
    )

    # --------------------------------------------------------
    # Update current proposal
    # --------------------------------------------------------

    proposal.version = next_version

    proposal.title = revision.title
    proposal.client_summary = revision.client_summary

    proposal.scope = revision.scope
    proposal.pages = revision.pages
    proposal.features = revision.features
    proposal.authentication = revision.authentication
    proposal.integrations = revision.integrations

    proposal.mobile = revision.mobile
    proposal.backend = revision.backend
    proposal.devops = revision.devops

    proposal.technical_scope = revision.technical_scope

    proposal.deliverables = revision.deliverables
    proposal.assumptions = revision.assumptions
    proposal.exclusions = revision.exclusions

    proposal.timeline = revision.timeline
    proposal.milestones = revision.milestones

    proposal.country = revision.country
    proposal.currency = revision.currency

    proposal.total_price = revision.total_price

    proposal.pricing_snapshot = revision.pricing_snapshot
    proposal.ai_analysis = revision.ai_analysis

    proposal.save()

    return revision


@transaction.atomic
def create_initial_proposal(
    *,
    lead,
    data,
    project_request=None,
    quote_request=None,
    source="project_request",
    created_by=None,
):
    """
    Creates the proposal and its first revision.
    """

    proposal = Proposal.objects.create(
        lead=lead,

        project_request=project_request,
        quote_request=quote_request,

        source=source,

        status="draft",

        title=data.get(
            "title",
            "AB Technologies Proposal",
        ),

        created_by=created_by,

        country=data.get(
            "country",
            getattr(lead, "country", ""),
        ),

        currency=data.get(
            "currency",
            getattr(
                lead,
                "preferred_currency",
                "",
            ) or "NGN",
        ),
    )

    revision = save_proposal_revision(
        proposal=proposal,
        data=data,
        source="ai",
        change_summary="Initial AI-generated proposal.",
    )

    return proposal, revision


@transaction.atomic
def accept_proposal(proposal):
    """
    Freeze the currently active proposal version.

    Once accepted, we DO NOT silently rewrite it.
    """

    if proposal.status == "accepted":
        return proposal

    proposal.status = "accepted"
    proposal.accepted_version = proposal.version

    from django.utils import timezone

    proposal.accepted_at = timezone.now()

    proposal.save(
        update_fields=[
            "status",
            "accepted_version",
            "accepted_at",
            "updated_at",
        ]
    )

    return proposal


from .proposal_ai import (
    generate_proposal_data,
    revise_proposal,
)


@transaction.atomic
def generate_proposal_revision(
    *,
    proposal,
    change_request,
    source="client",
):
    analysis = revise_proposal(
        proposal,
        change_request,
    )

    country = proposal.country
    currency = proposal.currency

    pricing = analysis.get(
        "pricing",
        {},
    )

    estimated_total = pricing.get(
        "estimated_total",
        proposal.total_price,
    )

    data = {
        "title": analysis.get(
            "title",
            proposal.title,
        ),

        "client_summary": analysis.get(
            "client_summary",
            "",
        ),

        "scope": analysis.get(
            "scope",
            {},
        ),

        "pages": analysis.get(
            "pages",
            [],
        ),

        "features": analysis.get(
            "features",
            [],
        ),

        "authentication": analysis.get(
            "authentication",
            {},
        ),

        "integrations": analysis.get(
            "integrations",
            [],
        ),

        "mobile": analysis.get(
            "mobile",
            {},
        ),

        "backend": analysis.get(
            "backend",
            {},
        ),

        "devops": analysis.get(
            "devops",
            {},
        ),

        "technical_scope": analysis.get(
            "technical_scope",
            {},
        ),

        "deliverables": analysis.get(
            "deliverables",
            [],
        ),

        "assumptions": analysis.get(
            "assumptions",
            [],
        ),

        "exclusions": analysis.get(
            "exclusions",
            [],
        ),

        "timeline": analysis.get(
            "timeline",
            {},
        ),

        "milestones": analysis.get(
            "milestones",
            [],
        ),

        "country": country,

        "currency": (
            pricing.get(
                "currency",
                currency,
            )
            or currency
        ),

        # AI revised estimate
        "total_price": estimated_total,

        # Internal only
        "pricing_snapshot": {
            "ai_estimated_total": estimated_total,

            "currency": (
                pricing.get(
                    "currency",
                    currency,
                )
                or currency
            ),

            "pricing_rationale": pricing.get(
                "pricing_rationale",
                "",
            ),

            "confidence": pricing.get(
                "confidence",
                "medium",
            ),

            "source": "gemini_revision",
        },

        # Internal only
        "ai_analysis": analysis,
    }

    revision = save_proposal_revision(
        proposal=proposal,
        data=data,
        source=source,
        change_summary=change_request,
    )

    return proposal, revision


def generate_initial_proposal(
    *,
    lead,
    project_request=None,
    quote_request=None,
    created_by=None,
):
    """
    Generate a brand-new proposal from a CRM request.
    """

    data = generate_proposal_data(
        lead=lead,
        project_request=project_request,
        quote_request=quote_request,
    )

    source = "project_request"

    if quote_request and not project_request:
        source = "quote_request"

    proposal, revision = create_initial_proposal(
        lead=lead,
        data=data,
        project_request=project_request,
        quote_request=quote_request,
        source=source,
        created_by=created_by,
    )

    return proposal, revision



# proposals/services.py

from decimal import Decimal

from django.db import transaction

from .models import Proposal, ProposalFeature


PRICED_STATUSES = {
    "confirmed",
    "recommended",
}
# proposals/services.py

from decimal import Decimal

from django.db import transaction

from .models import Proposal, ProposalFeature
from .pricing import calculate_feature_total


# ============================================================
# FEATURE TOTAL
# ============================================================

from decimal import Decimal

from django.db import transaction

from .models import Proposal, ProposalFeature
from .pricing import calculate_feature_total


# ============================================================
# FEATURE TOTAL
# ============================================================

def calculate_proposal_feature_total(feature):
    """
    Calculate the line total for a proposal feature.

    This is the feature's price, not necessarily the amount
    included in the proposal total.
    """

    quantity = feature.quantity or 1
    unit_price = feature.unit_price or Decimal("0")

    return (
        Decimal(quantity) * Decimal(unit_price)
    )


# ============================================================
# RECALCULATE PROPOSAL TOTAL
# ============================================================
def recalculate_proposal_total(proposal):
    """
    Calculate the current client-facing proposal total.

    INCLUDED:
        required + approved
        recommended + approved

    EXCLUDED:
        optional
        pending
        rejected
        removed

    Returns:
        Decimal
    """

    features = ProposalFeature.objects.filter(
        proposal=proposal
    )

    total = Decimal("0")

    for feature in features:

        # ----------------------------------------------------
        # Calculate the line price
        # ----------------------------------------------------

        quantity = feature.quantity or 1
        unit_price = feature.unit_price or Decimal("0")

        line_total = (
            Decimal(quantity) * Decimal(unit_price)
        )

        # Keep the feature's displayed price updated.
        if feature.total_price != line_total:
            feature.total_price = line_total
            feature.save(
                update_fields=[
                    "total_price",
                    "updated_at",
                ]
            )

        # ----------------------------------------------------
        # Determine whether this feature is included
        # ----------------------------------------------------

        if feature.status != "approved":
            continue

        if feature.scope_status not in {
            "required",
            "recommended",
        }:
            continue

        total += line_total

    # --------------------------------------------------------
    # Save proposal total
    # --------------------------------------------------------

    if proposal.total_price != total:
        proposal.total_price = total

        proposal.save(
            update_fields=[
                "total_price",
                "updated_at",
            ]
        )

    return total
# ============================================================
# CLIENT NEGOTIATION
# ============================================================

@transaction.atomic
def toggle_client_feature(feature):
    

    if feature.status != "approved":
        raise ValueError(
            "This feature is not available for selection."
        )

    if feature.scope_status == "recommended":
        feature.scope_status = "optional"
    elif feature.scope_status == "required":
        feature.scope_status = "optional"
    elif feature.scope_status == "optional":
        feature.scope_status = "recommended"
    else:
        raise ValueError(
            "Invalid feature scope."
        )

    feature.save(
        update_fields=[
            "scope_status",
            "updated_at",
        ]
    )

    total = recalculate_proposal_total(feature.proposal)

    return feature, total

def get_pricing_rule(feature_key):
    """
    Find the active PricingRule for a feature key.
    """
    from .models import PricingRule

    return PricingRule.objects.filter(
        code=feature_key,
        is_active=True,
    ).first()


@transaction.atomic
def create_proposal_feature(
    proposal,
    feature_key,
    name=None,
    description="",
    category="",
    complexity="medium",
    quantity=1,
    status="optional",
    source="admin",
):
    """
    Create a ProposalFeature.

    If feature_key exists in PricingRule, pricing information
    is copied into the proposal as a pricing snapshot.
    """

    pricing_rule = get_pricing_rule(feature_key)

    if pricing_rule:
        name = name or pricing_rule.name
        category = category or pricing_rule.category
        unit_price = pricing_rule.price
    else:
        # Admin may manually create a feature, but it will not
        # automatically receive catalog pricing.
        name = name or feature_key
        unit_price = Decimal("0")

    feature = ProposalFeature.objects.create(
        proposal=proposal,
        feature_key=feature_key,
        name=name,
        description=description,
        category=category,
        complexity=complexity,
        quantity=max(int(quantity or 1), 1),
        unit_price=unit_price,
        status=status,
        source=source,
    )

    feature.total_price = calculate_proposal_feature_total(feature)
    feature.save(update_fields=["total_price", "updated_at"])

    recalculate_proposal_total(proposal)

    return feature