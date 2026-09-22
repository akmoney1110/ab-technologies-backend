
from decimal import Decimal
from copy import deepcopy

from django.db import transaction
from django.utils import timezone

from proposals.models import (
    Proposal,
    ProposalFeature,
    ProposalRequirement,
    ProposalScreen,
    ProposalRevision,
)

from .pricing import calculate_price


# ============================================================
# CONSTANTS
# ============================================================

ACTIVE_FEATURE_STATUSES = {
    "pending",
    "approved",
}

REMOVED_FEATURE_STATUSES = {
    "removed",
    "rejected",
}

SCOPE_STATUSES = {
    "required",
    "recommended",
    "optional",
}

REQUIREMENT_TYPES = {
    "confirmed",
    "recommended",
    "optional",
    "future",
}


# ============================================================
# GENERIC HELPERS
# ============================================================

def as_dict(value):
    if isinstance(value, dict):
        return value

    return {}


def as_list(value):
    if isinstance(value, list):
        return value

    return []


def safe_int(value, default=1):
    try:
        value = int(value)

        if value < 1:
            return default

        return value

    except (TypeError, ValueError):
        return default


def safe_decimal(value, default=Decimal("0")):
    try:
        return Decimal(str(value))
    except Exception:
        return default


def clean_text(value, default=""):
    if value is None:
        return default

    return str(value).strip()


# ============================================================
# REQUIREMENT NORMALIZATION
# ============================================================

def normalize_requirement(item):
    """
    Convert either:

        "User registration"

    or:

        {
            "title": "...",
            "description": "..."
        }

    into a consistent structure.
    """

    if isinstance(item, str):

        return {
            "title": item.strip(),
            "description": "",
        }

    if isinstance(item, dict):

        title = (
            item.get("title")
            or item.get("name")
            or item.get("requirement")
            or item.get("text")
            or ""
        )

        description = (
            item.get("description")
            or item.get("details")
            or ""
        )

        return {
            "title": clean_text(title),
            "description": clean_text(description),
        }

    return {
        "title": "",
        "description": "",
    }


# ============================================================
# SAVE REQUIREMENTS
# ============================================================

def save_proposal_requirements(
    proposal,
    analysis,
    *,
    replace=True,
):
    """
    Save AI/client requirements into ProposalRequirement.

    confirmed_requirements
        -> confirmed

    recommended_requirements
        -> recommended

    optional_future_features
        -> optional

    Anything explicitly marked future can be saved as future.
    """

    if replace:
        proposal.requirements.all().delete()

    groups = [
        (
            "confirmed_requirements",
            "confirmed",
        ),
        (
            "recommended_requirements",
            "recommended",
        ),
        (
            "optional_future_features",
            "optional",
        ),
    ]

    sort_order = 0

    objects = []

    for field_name, requirement_type in groups:

        items = as_list(
            analysis.get(field_name)
        )

        for item in items:

            data = normalize_requirement(item)

            if not data["title"]:
                continue

            objects.append(
                ProposalRequirement(
                    proposal=proposal,
                    title=data["title"],
                    description=data["description"],
                    requirement_type=requirement_type,
                    status="pending",
                    source="ai",
                    sort_order=sort_order,
                )
            )

            sort_order += 1

    if objects:
        ProposalRequirement.objects.bulk_create(
            objects
        )

    return list(
        proposal.requirements.order_by(
            "sort_order"
        )
    )


# ============================================================
# SCREEN NORMALIZATION
# ============================================================
# ============================================================
# SCREEN NORMALIZATION
# ============================================================

def normalize_screen(item):

    if isinstance(item, str):
        return {
            "name": item.strip(),
            "screen_type": "",
            "purpose": "",
            "user_roles": [],
            "key_functionality": [],
            "major_components": [],
            "data_involved": [],
            "actions": [],
            "complexity": "",
            "dependencies": [],
            "status": "confirmed",
        }

    if not isinstance(item, dict):
        return {
            "name": "",
            "screen_type": "",
            "purpose": "",
            "user_roles": [],
            "key_functionality": [],
            "major_components": [],
            "data_involved": [],
            "actions": [],
            "complexity": "",
            "dependencies": [],
            "status": "confirmed",
        }

    return {
        "name": clean_text(
            item.get("name")
            or item.get("title")
            or item.get("screen")
        ),

        "screen_type": clean_text(
            item.get("screen_type")
            or item.get("type")
        ),

        "purpose": clean_text(
            item.get("purpose")
            or item.get("description")
        ),

        "user_roles": as_list(
            item.get("user_roles")
            or item.get("user_role")
            or item.get("user_type")
            or item.get("role")
        ),

        "key_functionality": as_list(
            item.get("key_functionality")
            or item.get("functionality")
            or item.get("features")
        ),

        "major_components": as_list(
            item.get("major_components")
            or item.get("components")
        ),

        "data_involved": as_list(
            item.get("data_involved")
            or item.get("data")
        ),

        "actions": as_list(
            item.get("actions")
        ),

        "complexity": clean_text(
            item.get("complexity")
        ),

        "dependencies": as_list(
            item.get("dependencies")
        ),

        "status": clean_text(
            item.get("status")
            or "confirmed"
        ),
    }


# ============================================================
# SAVE SCREENS
# ============================================================

def save_proposal_screens(
    proposal,
    analysis,
    *,
    replace=True,
):
    """
    Save pages/screens into ProposalScreen.

    The AI can use different names for some fields,
    but everything is normalized into the actual
    ProposalScreen model fields.
    """

    if replace:
        proposal.screens.all().delete()

    pages = as_list(
        analysis.get("pages")
    )

    objects = []

    for index, item in enumerate(pages):

        data = normalize_screen(item)

        if not data["name"]:
            continue

        objects.append(
            ProposalScreen(
                proposal=proposal,

                name=data["name"],

                screen_type=data["screen_type"],

                purpose=data["purpose"],

                user_roles=data["user_roles"],

                key_functionality=data[
                    "key_functionality"
                ],

                major_components=data[
                    "major_components"
                ],

                data_involved=data[
                    "data_involved"
                ],

                actions=data["actions"],

                complexity=data["complexity"],

                dependencies=data[
                    "dependencies"
                ],

                status=data["status"],

                sort_order=index,
            )
        )

    if objects:
        ProposalScreen.objects.bulk_create(
            objects
        )

    return list(
        proposal.screens.order_by(
            "sort_order"
        )
    )

# ============================================================
# FEATURE NORMALIZATION
# ============================================================

def normalize_feature(item):

    if not isinstance(item, dict):
        return None

    feature_key = clean_text(
        item.get("feature_key")
    )

    if not feature_key:
        return None

    scope_status = clean_text(
        item.get("scope_status")
        or "required"
    ).lower()

    if scope_status not in SCOPE_STATUSES:
        scope_status = "required"

    complexity = clean_text(
        item.get("complexity")
        or "medium"
    ).lower()

    if complexity not in {
        "low",
        "medium",
        "high",
    }:
        complexity = "medium"

    quantity = safe_int(
        item.get("quantity"),
        default=1,
    )

    return {
        "feature_key": feature_key,

        "name": clean_text(
            item.get("name")
            or feature_key.replace(
                "_",
                " "
            ).title()
        ),

        "description": clean_text(
            item.get("description")
        ),

        "category": clean_text(
            item.get("category")
        ),

        "complexity": complexity,

        "quantity": quantity,

        "scope_status": scope_status,
    }


# ============================================================
# GET ALL PRICING FEATURES
# ============================================================

def get_all_pricing_features(analysis):
    """
    Collect:

        pricing_basis
        recommended_pricing
        optional_pricing

    into one list.

    AI monetary values are deliberately ignored.
    """

    pricing = as_dict(
        analysis.get("pricing")
    )

    groups = [
        (
            "pricing_basis",
            "required",
        ),
        (
            "recommended_pricing",
            "recommended",
        ),
        (
            "optional_pricing",
            "optional",
        ),
    ]

    result = []

    for field_name, default_scope in groups:

        items = as_list(
            pricing.get(field_name)
        )

        for item in items:

            if not isinstance(item, dict):
                continue

            item = deepcopy(item)

            # Backend controls scope.
            item["scope_status"] = (
                default_scope
            )

            normalized = normalize_feature(
                item
            )

            if normalized:
                result.append(
                    normalized
                )

    return result


# ============================================================
# SAVE FEATURES
# ============================================================

def save_proposal_features(
    proposal,
    analysis,
    *,
    replace=True,
):
    """
    Save all pricing features.

    IMPORTANT:

    AI does NOT control:

        unit_price
        total_price

    Python pricing engine controls them.
    """

    if replace:
        proposal.proposal_features.all().delete()

    features = get_all_pricing_features(
        analysis
    )

    objects = []

    for index, feature in enumerate(features):

        feature_key = feature[
            "feature_key"
        ]

        complexity = feature[
            "complexity"
        ]

        quantity = feature[
            "quantity"
        ]

        # ----------------------------------------------------
        # AUTHORITATIVE BACKEND PRICE
        # ----------------------------------------------------

        unit_price = safe_decimal(
            calculate_price(
                feature_key,
                complexity=complexity,
            )
        )

        total_price = (
            unit_price
            * quantity
        )

        objects.append(
            ProposalFeature(
                proposal=proposal,

                feature_key=feature_key,

                name=feature["name"],

                description=feature[
                    "description"
                ],

                category=feature[
                    "category"
                ],

                complexity=complexity,

                quantity=quantity,

                unit_price=unit_price,

                total_price=total_price,

                scope_status=feature[
                    "scope_status"
                ],

                status="approved",

                source="ai",

                sort_order=index,
            )
        )

    if objects:

        ProposalFeature.objects.bulk_create(
            objects
        )

    return list(
        proposal.proposal_features.order_by(
            "sort_order"
        )
    )


# ============================================================
# SAVE PROPOSAL JSON MIRROR
# ============================================================

def sync_proposal_json_fields(
    proposal,
    analysis,
):
    """
    Keep the existing Proposal JSON fields populated.

    This is important because your frontend currently expects
    fields such as:

        pages
        features
        integrations
        backend
        mobile
        devops

    while the normalized tables become the editable source
    of truth.
    """

    proposal.executive_summary = (
        analysis.get(
            "executive_summary",
            proposal.client_summary or "",
        )
    )

    proposal.client_summary = (
        analysis.get(
            "client_summary",
            proposal.client_summary or "",
        )
    )

    proposal.business_objectives = (
        as_list(
            analysis.get(
                "business_objectives"
            )
        )
    )

    proposal.confirmed_requirements = (
        as_list(
            analysis.get(
                "confirmed_requirements"
            )
        )
    )

    proposal.recommended_requirements = (
        as_list(
            analysis.get(
                "recommended_requirements"
            )
        )
    )

    proposal.optional_future_features = (
        as_list(
            analysis.get(
                "optional_future_features"
            )
        )
    )

    proposal.security = as_dict(
        analysis.get("security")
    )

    proposal.recurring_costs = (
        as_list(
            analysis.get(
                "recurring_costs"
            )
        )
    )

    proposal.scope = as_dict(
        analysis.get("scope")
    )

    proposal.pages = as_list(
        analysis.get("pages")
    )

    proposal.features = as_list(
        analysis.get("features")
    )

    proposal.authentication = as_dict(
        analysis.get("authentication")
    )

    proposal.integrations = as_list(
        analysis.get("integrations")
    )

    proposal.mobile = as_dict(
        analysis.get("mobile")
    )

    proposal.backend = as_dict(
        analysis.get("backend")
    )

    proposal.devops = as_dict(
        analysis.get("devops")
    )

    proposal.technical_scope = as_dict(
        analysis.get("technical_scope")
    )

    proposal.deliverables = as_list(
        analysis.get("deliverables")
    )

    proposal.assumptions = as_list(
        analysis.get("assumptions")
    )

    proposal.exclusions = as_list(
        analysis.get("exclusions")
    )

    proposal.timeline = as_dict(
        analysis.get("timeline")
    )

    proposal.milestones = as_list(
        analysis.get("milestones")
    )

    return proposal


# ============================================================
# REBUILD FEATURE PRICING
# ============================================================

def recalculate_proposal_features(
    proposal,
):
    """
    Recalculate every active feature from the
    current pricing catalog.

    This means an admin can change:

        quantity
        complexity
        feature

    and the price is recalculated.

    AI prices are never trusted.
    """

    features = proposal.proposal_features.all()

    required_total = Decimal("0")
    recommended_total = Decimal("0")
    optional_total = Decimal("0")

    pricing_items = []

    for feature in features:

        if feature.status in (
            "removed",
            "rejected",
        ):

            feature.unit_price = Decimal("0")
            feature.total_price = Decimal("0")

            feature.save(
                update_fields=[
                    "unit_price",
                    "total_price",
                    "updated_at",
                ]
            )

            continue

        unit_price = safe_decimal(
            calculate_price(
                feature.feature_key,
                complexity=feature.complexity,
            )
        )

        total_price = (
            unit_price
            * feature.quantity
        )

        feature.unit_price = (
            unit_price
        )

        feature.total_price = (
            total_price
        )

        feature.save(
            update_fields=[
                "unit_price",
                "total_price",
                "updated_at",
            ]
        )

        if (
            feature.scope_status
            == "required"
        ):
            required_total += (
                total_price
            )

        elif (
            feature.scope_status
            == "recommended"
        ):
            recommended_total += (
                total_price
            )

        elif (
            feature.scope_status
            == "optional"
        ):
            optional_total += (
                total_price
            )

        pricing_items.append(
            {
                "name": feature.name,

                "feature_key": (
                    feature.feature_key
                ),

                "category": (
                    feature.category
                ),

                "scope_status": (
                    feature.scope_status
                ),

                "complexity": (
                    feature.complexity
                ),

                "quantity": (
                    feature.quantity
                ),

                "description": (
                    feature.description
                ),

                "unit_price": str(
                    unit_price
                ),

                "total": str(
                    total_price
                ),
            }
        )

    # --------------------------------------------------------
    # REQUIRED FEATURES ONLY
    # --------------------------------------------------------

    estimated_total = required_total

    return {
        "required_total": (
            required_total
        ),

        "recommended_total": (
            recommended_total
        ),

        "optional_total": (
            optional_total
        ),

        "subtotal": (
            required_total
        ),

        "adjustments": Decimal("0"),

        "estimated_total": (
            estimated_total
        ),

        "items": pricing_items,
    }


# ============================================================
# BUILD PRICING SNAPSHOT
# ============================================================

def build_pricing_snapshot(
    proposal,
    pricing,
):
    return {
        "source": (
            "database_pricing_catalog"
        ),

        "catalog_version": "current",

        "currency": proposal.currency,

        "required_total": str(
            pricing[
                "required_total"
            ]
        ),

        "recommended_total": str(
            pricing[
                "recommended_total"
            ]
        ),

        "optional_total": str(
            pricing[
                "optional_total"
            ]
        ),

        "subtotal": str(
            pricing[
                "subtotal"
            ]
        ),

        "adjustments": str(
            pricing[
                "adjustments"
            ]
        ),

        "estimated_total": str(
            pricing[
                "estimated_total"
            ]
        ),

        "items": pricing[
            "items"
        ],

        "calculated_at": (
            timezone.now().isoformat()
        ),
    }


# ============================================================
# RECALCULATE COMPLETE PROPOSAL
# ============================================================

@transaction.atomic
def recalculate_proposal(proposal):
    proposal = (
        Proposal.objects
        .select_for_update()
        .get(pk=proposal.pk)
    )

    # --------------------------------------------------------
    # PROCUREMENT PROPOSALS
    # --------------------------------------------------------
    # Procurement pricing comes from QuoteRequest /
    # accepted ProcurementClientRevision.
    #
    # Do NOT calculate procurement pricing from
    # ProposalFeature records.
    # --------------------------------------------------------
    if proposal.quote_request_id:
        proposal.pricing_snapshot = {
            "source": "procurement_quote",
            "currency": proposal.currency,
            "quote_request_id": str(
                proposal.quote_request_id
            ),
            "quote_total": str(
                proposal.quote_request.total or Decimal("0.00")
            ),
            "calculated_at": timezone.now().isoformat(),
        }

        proposal.save(
            update_fields=[
                "pricing_snapshot",
                "updated_at",
            ]
        )

        return proposal

    # --------------------------------------------------------
    # SOFTWARE / PROJECT PROPOSALS
    # --------------------------------------------------------

    pricing = recalculate_proposal_features(
        proposal
    )

    proposal.total_price = (
        pricing["estimated_total"]
    )

    proposal.pricing_snapshot = (
        build_pricing_snapshot(
            proposal,
            pricing,
        )
    )

    proposal.save(
        update_fields=[
            "total_price",
            "pricing_snapshot",
            "updated_at",
        ]
    )

    return proposal

# ============================================================
# CREATE COMPLETE PROPOSAL
# ============================================================

@transaction.atomic
def create_proposal_from_analysis(
    *,
    lead,
    analysis,
    source="project_request",
    project_request=None,
    quote_request=None,
    country="",
    currency="NGN",
    created_by=None,
):
    """
    COMPLETE persistence pipeline.
    """
    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------
    if not isinstance(analysis, dict):
        raise TypeError(
            "create_proposal_from_analysis() expected "
            "analysis to be a dict, but received "
            f"{type(analysis).__name__}: {analysis!r}"
        )
    # --------------------------------------------------------
    # CREATE PROPOSAL
    # --------------------------------------------------------
    proposal = Proposal.objects.create(
        lead=lead,
        project_request=project_request,
        quote_request=quote_request,
        source=source,
        version=1,
        title=analysis.get(
            "title",
            "AB Technologies Project Proposal",
        ),
        created_by=created_by,
        country=country,
        currency=(
            str(currency or "NGN")
            .strip()
            .upper()
        ),
        status="draft",
        ai_analysis=deepcopy(analysis),
    )
    # --------------------------------------------------------
    # MAIN JSON DATA
    # --------------------------------------------------------
    sync_proposal_json_fields(
        proposal,
        analysis,
    )
    proposal.save()
    # --------------------------------------------------------
    # NORMALIZED TABLES
    # --------------------------------------------------------
    save_proposal_requirements(
        proposal,
        analysis,
    )
    save_proposal_screens(
        proposal,
        analysis,
    )
    save_proposal_features(
        proposal,
        analysis,
    )
    # --------------------------------------------------------
    # FINAL AUTHORITATIVE PRICE
    # --------------------------------------------------------
    if not quote_request:

        save_proposal_features(

        proposal,

        analysis,

    )
    recalculate_proposal(proposal)
    proposal.refresh_from_db()
    return proposal

# ============================================================
# SNAPSHOT CURRENT PROPOSAL
# ============================================================

def build_revision_snapshot(
    proposal,
):
    """
    Convert the current Proposal into a
    complete immutable JSON snapshot.
    """

    features = []

    for feature in (
        proposal.proposal_features
        .all()
        .order_by("sort_order")
    ):

        features.append(
            {
                "feature_key": (
                    feature.feature_key
                ),

                "name": feature.name,

                "description": (
                    feature.description
                ),

                "category": (
                    feature.category
                ),

                "complexity": (
                    feature.complexity
                ),

                "quantity": (
                    feature.quantity
                ),

                "unit_price": str(
                    feature.unit_price
                ),

                "total_price": str(
                    feature.total_price
                ),

                "scope_status": (
                    feature.scope_status
                ),

                "status": (
                    feature.status
                ),

                "source": (
                    feature.source
                ),
            }
        )

    requirements = []

    for requirement in (
        proposal.requirements
        .all()
        .order_by("sort_order")
    ):

        requirements.append(
            {
                "title": requirement.title,

                "description": (
                    requirement.description
                ),

                "requirement_type": (
                    requirement.requirement_type
                ),

                "status": (
                    requirement.status
                ),

                "source": (
                    requirement.source
                ),
            }
        )

        screens = []

    for screen in (
        proposal.screens
        .all()
        .order_by("sort_order")
    ):

        screens.append(
            {
                "name": screen.name,

                "screen_type": (
                    screen.screen_type
                ),

                "purpose": screen.purpose,

                "user_roles": (
                    screen.user_roles
                ),

                "key_functionality": (
                    screen.key_functionality
                ),

                "major_components": (
                    screen.major_components
                ),

                "data_involved": (
                    screen.data_involved
                ),

                "actions": (
                    screen.actions
                ),

                "complexity": (
                    screen.complexity
                ),

                "dependencies": (
                    screen.dependencies
                ),

                "status": screen.status,
            }
        )

    return {
        "title": proposal.title,

        "client_summary": (
            proposal.client_summary
        ),

        "scope": proposal.scope,

        "pages": proposal.pages,

        "features": proposal.features,

        "authentication": (
            proposal.authentication
        ),

        "integrations": (
            proposal.integrations
        ),

        "mobile": proposal.mobile,

        "backend": proposal.backend,

        "devops": proposal.devops,

        "technical_scope": (
            proposal.technical_scope
        ),

        "deliverables": (
            proposal.deliverables
        ),

        "assumptions": (
            proposal.assumptions
        ),

        "exclusions": (
            proposal.exclusions
        ),

        "timeline": proposal.timeline,

        "milestones": proposal.milestones,

        "country": proposal.country,

        "currency": proposal.currency,

        "total_price": str(
            proposal.total_price
        ),

        "pricing_snapshot": (
            proposal.pricing_snapshot
        ),

        "requirements": requirements,

        "screens": screens,

        "proposal_features": features,
    }


# ============================================================
# CREATE REVISION SNAPSHOT
# ============================================================

@transaction.atomic
def create_proposal_revision(
    proposal,
    *,
    source="staff",
    change_summary="",
):
    """
    Save the current proposal as a historical
    ProposalRevision.

    The revision is immutable history.
    """

    proposal.refresh_from_db()

    version = (
        proposal.version
    )

    snapshot = (
        build_revision_snapshot(
            proposal
        )
    )

    revision = ProposalRevision.objects.create(
        proposal=proposal,

        version=version,

        source=source,

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

        total_price=(
            proposal.total_price
        ),

        pricing_snapshot=(
            proposal.pricing_snapshot
        ),

        ai_analysis=(
            proposal.ai_analysis
        ),

        change_summary=(
            change_summary
        ),
    )

    return revision


# ============================================================
# UPDATE PROPOSAL FROM NEW AI ANALYSIS
# ============================================================

@transaction.atomic
def replace_proposal_from_analysis(
    proposal,
    analysis,
    *,
    source="ai",
    change_summary="",
    create_revision=True,
):
    """
    Replace the editable proposal with a new
    complete AI-generated analysis.

    Used by:

        AI regeneration
        AI revision
        major proposal changes
    """

    proposal = (
        Proposal.objects
        .select_for_update()
        .get(pk=proposal.pk)
    )

    if proposal.status == "accepted":
        raise ValueError(
            "Accepted proposals are frozen "
            "and cannot be modified."
        )

    if proposal.status == "cancelled":
        raise ValueError(
            "Cancelled proposals cannot be modified."
        )

    # --------------------------------------------------------
    # INCREMENT VERSION
    # --------------------------------------------------------

    proposal.version = (
        proposal.version + 1
    )

    # --------------------------------------------------------
    # PRESERVE AI SNAPSHOT
    # --------------------------------------------------------

    proposal.ai_analysis = (
        deepcopy(analysis)
    )

    # --------------------------------------------------------
    # UPDATE JSON FIELDS
    # --------------------------------------------------------

    proposal.title = analysis.get(
        "title",
        proposal.title,
    )

    sync_proposal_json_fields(
        proposal,
        analysis,
    )

    # --------------------------------------------------------
    # NORMALIZED CHILD TABLES
    # --------------------------------------------------------

    save_proposal_requirements(
        proposal,
        analysis,
        replace=True,
    )

    save_proposal_screens(
        proposal,
        analysis,
        replace=True,
    )

    save_proposal_features(
        proposal,
        analysis,
        replace=True,
    )

    proposal.status = "draft"

    proposal.save()

    # --------------------------------------------------------
    # AUTHORITATIVE PRICE
    # --------------------------------------------------------

    recalculate_proposal(
        proposal
    )

    # --------------------------------------------------------
    # REVISION HISTORY
    # --------------------------------------------------------

    if create_revision:

        create_proposal_revision(
            proposal,

            source=source,

            change_summary=(
                change_summary
            ),
        )

    proposal.refresh_from_db()

    return proposal

