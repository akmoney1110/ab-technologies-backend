from django.shortcuts import render

# Create your views here.
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from crm.models import Lead, ProjectRequest, QuoteRequest

from .models import Proposal
from .services import (
    generate_initial_proposal,
    generate_proposal_revision,
    accept_proposal,
)


# ============================================================
# HELPERS
# ============================================================

def proposal_to_dict(proposal, include_internal=False):
    """
    Convert Proposal into an API-safe dictionary.

    Payment information is calculated from the Proposal's
    financial records and is safe for both internal and
    client-facing proposal views.

    Internal AI analysis and pricing components are NOT returned
    unless explicitly requested internally.
    """

    next_payable = proposal.next_payable_milestone

    data = {
        "id": str(proposal.id),

        "title": proposal.title,

        "status": proposal.status,

        "version": proposal.version,

        "lead": {
            "id": str(proposal.lead.id),
            "name": proposal.lead.name,
            "company": proposal.lead.company,
        },

        "client_summary": proposal.client_summary,

        "country": proposal.country,

        "currency": proposal.currency,

        "total_price": str(
            proposal.total_price
        ),

        "formatted_price": proposal.formatted_price,

        # ====================================================
        # PAYMENT / FINANCIAL SUMMARY
        # ====================================================

        "payment": {
            "total": str(
                proposal.total_price
            ),

            "total_paid": str(
                proposal.total_paid
            ),

            "outstanding_balance": str(
                proposal.outstanding_balance
            ),

            "payment_status": (
                proposal.payment_status
            ),

            "payment_percentage": str(
                proposal.payment_percentage
            ),

            "formatted_total_paid": (
                proposal.formatted_total_paid
            ),

            "formatted_outstanding_balance": (
                proposal.formatted_outstanding_balance
            ),

            "milestone_count": (
                proposal.milestone_count
            ),

            "payment_required_milestone_count": (
                proposal.payment_required_milestone_count
            ),

            "paid_milestone_count": (
                proposal.paid_milestone_count
            ),

            "last_payment_at": (
                proposal.last_payment_at.isoformat()
                if proposal.last_payment_at
                else None
            ),

            "next_payable_milestone": (
                {
                    "id": str(next_payable.id),
                    "order": next_payable.order,
                    "title": next_payable.title,
                    "amount": str(
                        next_payable.amount
                    ),
                    "total_paid": str(
                        next_payable.total_paid
                    ),
                    "outstanding_balance": str(
                        next_payable.outstanding_balance
                    ),
                    "payment_status": (
                        next_payable.payment_status
                    ),
                    "status": next_payable.status,
                    "payment_required": (
                        next_payable.payment_required
                    ),
                }
                if next_payable
                else None
            ),
        },

        # ====================================================
        # COMPLETE CLIENT SCOPE
        # ====================================================

        "scope": proposal.scope,

        "pages": proposal.pages,

        "features": proposal.features,

        "authentication": proposal.authentication,

        "integrations": proposal.integrations,

        "mobile": proposal.mobile,

        "backend": proposal.backend,

        "devops": proposal.devops,

        "technical_scope": proposal.technical_scope,

        "deliverables": proposal.deliverables,

        "assumptions": proposal.assumptions,

        "exclusions": proposal.exclusions,

        "timeline": proposal.timeline,

        "milestones": proposal.milestones,

        "client_editable": proposal.client_editable,

        "accepted_version": proposal.accepted_version,

        "expires_at": (
            proposal.expires_at.isoformat()
            if proposal.expires_at
            else None
        ),

        "sent_at": (
            proposal.sent_at.isoformat()
            if proposal.sent_at
            else None
        ),

        "viewed_at": (
            proposal.viewed_at.isoformat()
            if proposal.viewed_at
            else None
        ),

        "accepted_at": (
            proposal.accepted_at.isoformat()
            if proposal.accepted_at
            else None
        ),

        "created_at": (
            proposal.created_at.isoformat()
        ),

        "updated_at": (
            proposal.updated_at.isoformat()
        ),
    }

    # ========================================================
    # INTERNAL ADMIN DATA
    # ========================================================

    if include_internal:

        data["internal"] = {
            "pricing_snapshot": (
                proposal.pricing_snapshot
            ),

            "ai_analysis": (
                proposal.ai_analysis
            ),
        }

    return data

# ============================================================
# GENERATE
# ============================================================



import json
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import (
    Proposal,
    ProposalFeature,
    ProposalRequirement,
    ProposalScreen,
    ProposalComment,
)

from .services import (
    recalculate_proposal_total,
)

def get_client_request_data(request):
    try:
        if not request.body:
            return {}

        data = json.loads(request.body)

        if not isinstance(data, dict):
            return {}

        return data

    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}















@api_view(["POST"])
def generate(request):
    """
    Generate a proposal from a CRM request.

    Expected:

    {
        "lead_id": "...",
        "project_request_id": "..."
    }

    OR:

    {
        "lead_id": "...",
        "quote_request_id": "..."
    }
    """

    lead_id = request.data.get(
        "lead_id"
    )

    project_request_id = request.data.get(
        "project_request_id"
    )

    quote_request_id = request.data.get(
        "quote_request_id"
    )

    if not lead_id:
        return Response(
            {
                "success": False,
                "error": "lead_id is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        lead = Lead.objects.get(
            id=lead_id
        )

    except Lead.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Lead not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    project_request = None
    quote_request = None

    if project_request_id:

        try:
            project_request = ProjectRequest.objects.get(
                id=project_request_id
            )

        except ProjectRequest.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Project request not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    elif quote_request_id:

        try:
            quote_request = QuoteRequest.objects.get(
                id=quote_request_id
            )

        except QuoteRequest.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Quote request not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    else:

        return Response(
            {
                "success": False,
                "error": (
                    "Provide either project_request_id "
                    "or quote_request_id."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:

        proposal, revision = generate_initial_proposal(
            lead=lead,
            project_request=project_request,
            quote_request=quote_request,
            created_by=(
                request.user
                if request.user.is_authenticated
                else None
            ),
        )

    except Exception as exc:

        return Response(
            {
                "success": False,
                "error": str(exc),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "success": True,
            "proposal": proposal_to_dict(
                proposal,
                include_internal=True,
            ),
            "revision": {
                "id": str(revision.id),
                "version": revision.version,
            },
        },
        status=status.HTTP_201_CREATED,
    )


# ============================================================
# GET PROPOSAL
# ============================================================

@api_view(["GET"])
def detail(request, proposal_id):
    """
    Return the current proposal.

    Internal pricing information is returned only to staff.
    """

    try:
        proposal = Proposal.objects.select_related(
            "lead"
        ).get(
            id=proposal_id
        )

    except Proposal.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Proposal not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    is_internal = (
        request.user.is_authenticated
        and request.user.is_staff
    )

    # --------------------------------------------------------
    # Mark as viewed
    # --------------------------------------------------------

    if proposal.status == "sent":

        proposal.status = "viewed"
        proposal.viewed_at = timezone.now()

        proposal.save(
            update_fields=[
                "status",
                "viewed_at",
                "updated_at",
            ]
        )

    return Response(
        {
            "success": True,
            "proposal": proposal_to_dict(
                proposal,
                include_internal=is_internal,
            ),
        }
    )


# ============================================================
# REVISE
# ============================================================
from django.db import transaction
@api_view(["POST"])
def revise(request, proposal_id):
    change_request = request.data.get("change_request", "").strip()

    if not change_request:
        return Response(
            {
                "success": False,
                "error": "change_request is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():

        proposal = (
            Proposal.objects
            .select_for_update()
            .select_related("lead")
            .get(id=proposal_id)
        )

        if proposal.status == "accepted":
            return Response(
                {
                    "success": False,
                    "error": "This proposal has already been accepted and is frozen.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not proposal.client_editable:
            return Response(
                {
                    "success": False,
                    "error": "This proposal cannot be edited.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        proposal, revision = generate_proposal_revision(
            proposal=proposal,
            change_request=change_request,
            source="client",
        )

    return Response(
        {
            "success": True,
            "proposal": proposal_to_dict(
                proposal,
                include_internal=False,
            ),
            "revision": {
                "id": str(revision.id),
                "version": revision.version,
                "source": revision.source,
                "change_summary": revision.change_summary,
                "created_at": revision.created_at,
            },
        },
        status=status.HTTP_200_OK,
    )


# ============================================================
# ACCEPT
# ============================================================

@api_view(["POST"])
def accept(request, proposal_id):
    """
    Accept the current proposal version.

    The current version becomes the agreed scope.
    """

    try:

        proposal = Proposal.objects.get(
            id=proposal_id
        )

    except Proposal.DoesNotExist:

        return Response(
            {
                "success": False,
                "error": "Proposal not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if proposal.status == "accepted":

        return Response(
            {
                "success": True,
                "message": "Proposal is already accepted.",
                "proposal": proposal_to_dict(
                    proposal
                ),
            }
        )

    if proposal.status not in {
        "sent",
        "viewed",
        "ready",
        "draft",
        "revision_requested",
    }:

        return Response(
            {
                "success": False,
                "error": (
                    "This proposal cannot be accepted "
                    "in its current state."
                ),
            },
            status=status.HTTP_409_CONFLICT,
        )

    proposal = accept_proposal(
        proposal
    )

    return Response(
        {
            "success": True,

            "message": (
                f"Proposal version "
                f"{proposal.accepted_version} "
                f"has been accepted."
            ),

            "proposal": proposal_to_dict(
                proposal
            ),
        }
    )


# ============================================================
# REVISIONS
# ============================================================

@api_view(["GET"])
def revisions(request, proposal_id):
    """
    Return proposal history.

    Internal pricing details are only exposed to staff.
    """

    try:

        proposal = Proposal.objects.get(
            id=proposal_id
        )

    except Proposal.DoesNotExist:

        return Response(
            {
                "success": False,
                "error": "Proposal not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    is_internal = (
        request.user.is_authenticated
        and request.user.is_staff
    )

    revision_list = []

    for revision in proposal.revisions.all():

        item = {
            "id": str(revision.id),

            "version": revision.version,

            "source": revision.source,

            "title": revision.title,

            "client_summary": revision.client_summary,

            "scope": revision.scope,

            "pages": revision.pages,

            "features": revision.features,

            "authentication": revision.authentication,

            "integrations": revision.integrations,

            "mobile": revision.mobile,

            "backend": revision.backend,

            "devops": revision.devops,

            "technical_scope": revision.technical_scope,

            "deliverables": revision.deliverables,

            "assumptions": revision.assumptions,

            "exclusions": revision.exclusions,

            "timeline": revision.timeline,

            "milestones": revision.milestones,

            "country": revision.country,

            "currency": revision.currency,

            "total_price": str(
                revision.total_price
            ),

            "change_summary": revision.change_summary,

            "created_at": revision.created_at.isoformat(),
        }

        if is_internal:

            item["pricing_snapshot"] = (
                revision.pricing_snapshot
            )

            item["ai_analysis"] = (
                revision.ai_analysis
            )

        revision_list.append(item)

    return Response(
        {
            "success": True,

            "proposal_id": str(
                proposal.id
            ),

            "current_version": proposal.version,

            "accepted_version": (
                proposal.accepted_version
            ),

            "revisions": revision_list,
        }
    )






from django.urls import reverse
# ============================================================
# ADMIN REVIEW
# ============================================================

def admin_review(request, proposal_id):
    """
    Render the internal AB Technologies proposal review workspace.

    This page is for staff only.

    Internal AI analysis and pricing information are intentionally
    available here because this is an internal admin page.
    They are never exposed through the public proposal endpoint.
    """

    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(
            request.get_full_path()
        )

    if not request.user.is_staff:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied

    try:

        proposal = (
            Proposal.objects
            .select_related("lead")
            .prefetch_related("revisions")
            .get(id=proposal_id)
        )

    except Proposal.DoesNotExist:

        from django.http import Http404

        raise Http404("Proposal not found.")

    # ========================================================
    # AI ANALYSIS
    # ========================================================

    ai_analysis = proposal.ai_analysis or {}

    if not isinstance(ai_analysis, dict):
        ai_analysis = {}


    # ========================================================
    # PRICING SNAPSHOT
    # ========================================================

    pricing_snapshot = proposal.pricing_snapshot or {}

    if not isinstance(pricing_snapshot, dict):
        pricing_snapshot = {}


    # AI pricing may be stored inside pricing_snapshot
    # or inside ai_analysis["pricing"] depending on the
    # proposal generation version.

    ai_pricing = ai_analysis.get(
        "pricing",
        {}
    )

    if not isinstance(ai_pricing, dict):
        ai_pricing = {}


    # ========================================================
    # BASIC PROPOSAL DATA
    # ========================================================

    pages = proposal.pages or []
    features = proposal.features or []
    authentication = proposal.authentication or {}
    integrations = proposal.integrations or []
    mobile = proposal.mobile or {}
    backend = proposal.backend or {}
    devops = proposal.devops or {}
    technical_scope = proposal.technical_scope or {}
    deliverables = proposal.deliverables or []
    assumptions = proposal.assumptions or []
    exclusions = proposal.exclusions or []
    timeline = proposal.timeline or {}
    milestones = proposal.milestones or []


    # ========================================================
    # NEW AI ANALYSIS SECTIONS
    # ========================================================

    business_objectives = ai_analysis.get(
        "business_objectives",
        []
    )

    confirmed_requirements = ai_analysis.get(
        "confirmed_requirements",
        []
    )

    recommended_requirements = ai_analysis.get(
        "recommended_requirements",
        []
    )

    optional_future_features = ai_analysis.get(
        "optional_future_features",
        []
    )

    security = ai_analysis.get(
        "security",
        {}
    )

    next_steps = ai_analysis.get(
        "next_steps",
        []
    )


    # ========================================================
    # AI ESTIMATED PRICE
    # ========================================================

    ai_estimated_total = (
        pricing_snapshot.get(
            "ai_estimated_total"
        )
    )

    if ai_estimated_total is None:

        ai_estimated_total = ai_pricing.get(
            "estimated_total"
        )


    # ========================================================
    # PRICING CURRENCY
    # ========================================================

    ai_pricing_currency = (
        pricing_snapshot.get(
            "currency"
        )
        or ai_pricing.get(
            "currency"
        )
        or proposal.currency
    )


    # ========================================================
    # PRICING CONFIDENCE
    # ========================================================

    pricing_confidence = (
        pricing_snapshot.get(
            "confidence"
        )
        or ai_pricing.get(
            "confidence"
        )
        or ""
    )


    # ========================================================
    # PRICING RATIONALE
    # ========================================================

    pricing_rationale = (
        pricing_snapshot.get(
            "pricing_rationale"
        )
        or ai_pricing.get(
            "pricing_rationale"
        )
        or ""
    )


    # ========================================================
    # PRICING BASIS
    # ========================================================

    pricing_basis = (
        pricing_snapshot.get(
            "pricing_basis"
        )
        or ai_pricing.get(
            "pricing_basis"
        )
        or []
    )


    # ========================================================
    # PRICING GUIDANCE
    # ========================================================

    pricing_guidance = (
        pricing_snapshot.get(
            "pricing_guidance"
        )
        or {}
    )


    # ========================================================
    # IF THE PRICING SNAPSHOT CONTAINS CATALOG
    # INFORMATION, EXPOSE IT TO THE ADMIN PAGE.
    # ========================================================

    if not pricing_guidance:

        pricing_guidance = (
            pricing_snapshot.get(
                "catalog"
            )
            or pricing_snapshot.get(
                "pricing_catalog"
            )
            or {}
        )


    # ========================================================
    # STATUS
    # ========================================================

    status_labels = dict(
        Proposal.STATUS_CHOICES
    )

    status_label = status_labels.get(
        proposal.status,
        proposal.status.replace(
            "_",
            " "
        ).title()
    )


    # ========================================================
    # ACTION PERMISSIONS
    # ========================================================

    can_send = proposal.status in {
        "draft",
        "ready",
        "revision_requested",
    }

    can_regenerate = proposal.status not in {
        "accepted",
        "cancelled",
    }


    # ========================================================
    # ADMIN URLS
    # ========================================================

    admin_change_url = reverse(
        "admin:proposals_proposal_change",
        args=[proposal.pk]
    )

    admin_list_url = reverse(
        "admin:proposals_proposal_changelist"
    )


    # ========================================================
    # CLIENT PROPOSAL URL
    # ========================================================

    from django.conf import settings

    frontend_url = getattr(
        settings,
        frontend_url = settings.FRONTEND_URL)

    client_proposal_url = (
        f"{frontend_url}/proposals/"
        f"{proposal.public_token}/"
    )


    # ========================================================
    # CONTEXT
    # ========================================================

    context = {

        # ----------------------------------------------------
        # Proposal
        # ----------------------------------------------------

        "proposal": proposal,

        "status_label": status_label,

        "can_send": can_send,

        "can_regenerate": can_regenerate,


        # ----------------------------------------------------
        # URLs
        # ----------------------------------------------------

        "admin_change_url":
            admin_change_url,

        "admin_list_url":
            admin_list_url,

        "client_proposal_url":
            client_proposal_url,


        # ----------------------------------------------------
        # Core proposal sections
        # ----------------------------------------------------

        "pages":
            pages,

        "features":
            features,

        "authentication":
            authentication,

        "integrations":
            integrations,

        "mobile":
            mobile,

        "backend":
            backend,

        "devops":
            devops,

        "technical_scope":
            technical_scope,

        "deliverables":
            deliverables,

        "assumptions":
            assumptions,

        "exclusions":
            exclusions,

        "timeline":
            timeline,

        "milestones":
            milestones,


        # ----------------------------------------------------
        # AI analysis sections
        # ----------------------------------------------------

        "business_objectives":
            business_objectives,

        "confirmed_requirements":
            confirmed_requirements,

        "recommended_requirements":
            recommended_requirements,

        "optional_future_features":
            optional_future_features,

        "security":
            security,

        "next_steps":
            next_steps,


        # ----------------------------------------------------
        # Pricing
        # ----------------------------------------------------

        "ai_estimated_total":
            ai_estimated_total,

        "ai_pricing_currency":
            ai_pricing_currency,

        "pricing_confidence":
            pricing_confidence,

        "pricing_rationale":
            pricing_rationale,

        "pricing_basis":
            pricing_basis,

        "pricing_guidance":
            pricing_guidance,


        # ----------------------------------------------------
        # Raw internal AI information
        # ----------------------------------------------------

        "ai_analysis":
            ai_analysis,

        "pricing_snapshot":
            pricing_snapshot,
    }


    return render(
        request,
        "admin/proposals/proposal_review.html",
        context
    )




# proposals/views.py

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import (
    Proposal,
    ProposalFeature,
    ProposalRequirement,
    ProposalScreen,
)
from .services import (
    recalculate_proposal_total,
    toggle_client_feature,
)


# ============================================================
# HELPERS
# ============================================================

def serialize_feature(feature):
    return {
        "id": str(feature.id),
        "feature_key": feature.feature_key,
        "name": feature.name,
        "description": feature.description,
        "category": feature.category,
        "complexity": feature.complexity,
        "quantity": feature.quantity,
        "unit_price": str(feature.unit_price),
        "total_price": str(feature.total_price),
        "scope_status": feature.scope_status,
        "status": feature.status,
        "source": feature.source,
        "sort_order": feature.sort_order,
    }


def serialize_requirement(requirement):
    return {
        "id": requirement.id,
        "title": requirement.title,
        "description": requirement.description,
        "requirement_type": requirement.requirement_type,
        "status": requirement.status,
        "source": requirement.source,
        "sort_order": requirement.sort_order,
    }


def serialize_screen(screen):
    return {
        "id": screen.id,
        "name": screen.name,
        "screen_type": screen.screen_type,
        "purpose": screen.purpose,
        "user_roles": screen.user_roles,
        "key_functionality": screen.key_functionality,
        "major_components": screen.major_components,
        "data_involved": screen.data_involved,
        "actions": screen.actions,
        "complexity": screen.complexity,
        "dependencies": screen.dependencies,
        "status": screen.status,
        "sort_order": screen.sort_order,
    }























# ============================================================
# QUOTATION SERIALIZATION
# ============================================================

def serialize_quotation_item(item):
    """
    Serialize a quotation item for client/staff API responses.

    Pricing comes directly from Django's quotation models.
    Gemini is never the source of these financial values.
    """

    return {
        "id": str(item.id),

        "category": item.category,

        "name": item.name,

        "brand": item.brand,

        "model": item.model,

        "description": item.description,

        "specifications": (
            item.specifications
            if isinstance(item.specifications, dict)
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
    }


def serialize_quotation(quotation):
    """
    Serialize the complete QuoteRequest.

    This is the commercial quotation attached to the proposal.
    """

    if not quotation:
        return None

    items = [
        serialize_quotation_item(item)
        for item in quotation.items.all().order_by(
            "created_at"
        )
    ]

    currency = quotation.currency or "NGN"

    return {
        "id": str(quotation.id),

        "title": quotation.title,

        "request_type": quotation.request_type,

        "description": quotation.description,

        "purpose": quotation.purpose,

        "notes": quotation.notes,

        "budget": (
            str(quotation.budget)
            if quotation.budget is not None
            else None
        ),

        "currency": currency,

        "deadline": (
            quotation.deadline.isoformat()
            if quotation.deadline
            else None
        ),

        "status": quotation.status,

        # ----------------------------------------------------
        # ITEMS
        # ----------------------------------------------------

        "items": items,

        "item_count": len(items),

        # ----------------------------------------------------
        # FINANCIALS
        # ----------------------------------------------------

        "subtotal": str(
            quotation.subtotal
        ),

        "discount": str(
            quotation.discount
        ),

        "tax": str(
            quotation.tax
        ),

        "delivery_fee": str(
            quotation.delivery_fee
        ),

        "total": str(
            quotation.total
        ),

        "formatted_subtotal": (
            f"{currency} "
            f"{quotation.subtotal:,.2f}"
        ),

        "formatted_discount": (
            f"{currency} "
            f"{quotation.discount:,.2f}"
        ),

        "formatted_tax": (
            f"{currency} "
            f"{quotation.tax:,.2f}"
        ),

        "formatted_delivery_fee": (
            f"{currency} "
            f"{quotation.delivery_fee:,.2f}"
        ),

        "formatted_total": (
            f"{currency} "
            f"{quotation.total:,.2f}"
        ),

        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

        "created_at": (
            quotation.created_at.isoformat()
            if quotation.created_at
            else None
        ),

        "updated_at": (
            quotation.updated_at.isoformat()
            if quotation.updated_at
            else None
        ),
    }

















# ============================================================
# CLIENT PROPOSAL API
# ============================================================
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

@require_GET
@csrf_exempt
def client_csrf_api(request):
    return JsonResponse({"success": True})





@require_GET
@csrf_exempt
def client_proposal_api(request, public_token):
    """
    Return the complete client-facing proposal.

    Includes:

    - Proposal information
    - Client information
    - Business objectives
    - Requirements
    - Features
    - Screens
    - Technical scope
    - Deliverables
    - Timeline
    - Milestones
    - Complete quotation
    - Quotation items
    - Authoritative quotation pricing

    Internal AI analysis and internal pricing data are NOT exposed.
    """

    print(">>> CLIENT PROPOSAL API REACHED <<<")

    proposal = get_object_or_404(
        Proposal.objects
        .select_related(
            "lead",
            "organization",
            "quote_request",
        )
        .prefetch_related(
            "proposal_features",
            "requirements",
            "screens",
            "quote_request__items",
        ),
        public_token=public_token,
    )

    # ========================================================
    # EXPIRY
    # ========================================================

    now = timezone.now()

    if (
        proposal.expires_at
        and now > proposal.expires_at
        and proposal.status != "accepted"
    ):
        if proposal.status != "expired":

            proposal.status = "expired"

            proposal.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return JsonResponse(
            {
                "success": False,

                "error": (
                    "This proposal has expired."
                ),

                "status": "expired",
            },
            status=410,
        )

    # ========================================================
    # VISIBILITY
    # ========================================================

    if proposal.status in {
        "cancelled",
        "rejected",
    }:
        return JsonResponse(
            {
                "success": False,

                "error": (
                    "This proposal is not available."
                ),

                "status": proposal.status,
            },
            status=403,
        )

    # ========================================================
    # MARK VIEWED
    # ========================================================

    if proposal.status == "sent":

        proposal.status = "viewed"

        proposal.viewed_at = now

        proposal.save(
            update_fields=[
                "status",
                "viewed_at",
                "updated_at",
            ]
        )

    # ========================================================
    # FINANCIAL SOURCE OF TRUTH
    # ========================================================
    #
    # IMPORTANT:
    #
    # Procurement proposal:
    #     QuoteRequest is the financial source of truth.
    #
    # Software / service proposal:
    #     Approved ProposalFeature records are the financial
    #     source of truth.
    #
    # We MUST NOT run recalculate_proposal_total() for a
    # procurement proposal because that helper is feature-based
    # and can overwrite proposal.total_price with 0.00 when the
    # procurement proposal has no priced ProposalFeature rows.
    # ========================================================

    quote_request = getattr(
        proposal,
        "quote_request",
        None,
    )

    if quote_request is not None:

        # ----------------------------------------------------
        # PROCUREMENT
        # ----------------------------------------------------
        #
        # The quotation has already been priced by the server.
        # client_update_quotation() is responsible for changing
        # saved quantities / included items and recalculating the
        # quotation.
        #
        # Here we simply synchronize Proposal.total_price with
        # the CURRENT SAVED quotation total.
        # ----------------------------------------------------

        quotation_total = (
            quote_request.total
            if quote_request.total is not None
            else 0
        )

        quotation_currency = (
            quote_request.currency
            or proposal.currency
            or "NGN"
        )

        update_fields = []

        if proposal.total_price != quotation_total:
            proposal.total_price = quotation_total
            update_fields.append("total_price")

        if proposal.currency != quotation_currency:
            proposal.currency = quotation_currency
            update_fields.append("currency")

        if update_fields:
            update_fields.append("updated_at")

            proposal.save(
                update_fields=update_fields
            )

        total = quotation_total

    else:

        # ----------------------------------------------------
        # SOFTWARE / SERVICE
        # ----------------------------------------------------

        total = recalculate_proposal_total(
            proposal
        )

    # Refresh after the financial calculation/synchronization so
    # everything below is serialized from the latest database state.
    proposal.refresh_from_db()

    # Refresh the related quotation too. refresh_from_db() on the
    # Proposal does not refresh an already-loaded related object.
    quote_request = getattr(
        proposal,
        "quote_request",
        None,
    )

    if quote_request is not None:
        quote_request.refresh_from_db()

    # ========================================================
    # QUOTATION
    # ========================================================

    quotation = serialize_quotation(
        quote_request
    )

    # ========================================================
    # FEATURES
    # ========================================================

    features = list(
        proposal.proposal_features.all().order_by(
            "sort_order",
            "created_at",
        )
    )

    required_features = [
        serialize_feature(feature)
        for feature in features
        if (
            feature.scope_status == "required"
            and feature.status == "approved"
        )
    ]

    recommended_features = [
        serialize_feature(feature)
        for feature in features
        if (
            feature.scope_status == "recommended"
            and feature.status == "approved"
        )
    ]

    optional_features = [
        serialize_feature(feature)
        for feature in features
        if (
            feature.scope_status == "optional"
            and feature.status == "approved"
        )
    ]

    # ========================================================
    # REQUIREMENTS
    # ========================================================

    requirements = [
        serialize_requirement(requirement)
        for requirement in proposal.requirements.all().order_by(
            "sort_order",
            "created_at",
        )
    ]

    # ========================================================
    # SCREENS
    # ========================================================

    screens = [
        serialize_screen(screen)
        for screen in proposal.screens.all().order_by(
            "sort_order",
            "created_at",
        )
    ]

    # ========================================================
    # CLIENT INFORMATION
    # ========================================================

    lead = proposal.lead

    client = {
        "id": (
            str(lead.id)
            if lead
            else None
        ),

        "name": (
            lead.name
            if lead
            else ""
        ),

        "company": (
            lead.company
            if lead
            else ""
        ),

        "email": (
            lead.email
            if lead
            else ""
        ),

        "phone": (
            lead.phone
            if lead
            else ""
        ),

        "country": (
            lead.country
            if lead
            else proposal.country
        ),

        "preferred_currency": (
            lead.preferred_currency
            if lead
            else proposal.currency
        ),
    }

    # ========================================================
    # RESPONSE
    # ========================================================

    return JsonResponse(
        {
            "success": True,

            "proposal": {

                # ------------------------------------------------
                # IDENTITY
                # ------------------------------------------------

                "id": str(
                    proposal.id
                ),

                "public_token": str(
                    proposal.public_token
                ),

                "title": proposal.title,

                "client_summary": (
                    proposal.client_summary
                ),

                # ------------------------------------------------
                # STATUS
                # ------------------------------------------------

                "status": proposal.status,

                "version": proposal.version,

                "accepted_version": (
                    proposal.accepted_version
                ),

                "client_editable": (
                    proposal.client_editable
                ),

                # ------------------------------------------------
                # CLIENT
                # ------------------------------------------------

                "client": client,

                # ------------------------------------------------
                # LOCATION / CURRENCY
                # ------------------------------------------------

                "country": proposal.country,

                "currency": proposal.currency,

                # ------------------------------------------------
                # FINANCIAL SUMMARY
                #
                # Proposal total is the proposal's current
                # calculated total.
                # ------------------------------------------------

                "total_price": str(
                    proposal.total_price
                ),

                "formatted_total": (
                    proposal.formatted_price
                ),

                # ------------------------------------------------
                # BUSINESS
                # ------------------------------------------------

                "business_objectives": (
                    proposal.business_objectives
                ),

                "confirmed_requirements": (
                    proposal.confirmed_requirements
                ),

                "recommended_requirements": (
                    proposal.recommended_requirements
                ),

                "optional_future_features": (
                    proposal.optional_future_features
                ),

                "security": proposal.security,

                "recurring_costs": (
                    proposal.recurring_costs
                ),

                # ------------------------------------------------
                # PROJECT SCOPE
                # ------------------------------------------------

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

                # ------------------------------------------------
                # DELIVERABLES
                # ------------------------------------------------

                "deliverables": (
                    proposal.deliverables
                ),

                "assumptions": (
                    proposal.assumptions
                ),

                "exclusions": (
                    proposal.exclusions
                ),

                # ------------------------------------------------
                # TIMELINE
                # ------------------------------------------------

                "timeline": proposal.timeline,

                "milestones": proposal.milestones,

                # ------------------------------------------------
                # STRUCTURED FEATURES
                # ------------------------------------------------

                "required_features": (
                    required_features
                ),

                "recommended_features": (
                    recommended_features
                ),

                "optional_features": (
                    optional_features
                ),

                # ------------------------------------------------
                # STRUCTURED REQUIREMENTS
                # ------------------------------------------------

                "requirements": requirements,

                # ------------------------------------------------
                # SCREENS
                # ------------------------------------------------

                "screens": screens,

                # ------------------------------------------------
                # QUOTATION
                # ------------------------------------------------

                "quotation": quotation,

                # ------------------------------------------------
                # DATES
                # ------------------------------------------------

                "expires_at": (
                    proposal.expires_at.isoformat()
                    if proposal.expires_at
                    else None
                ),

                "sent_at": (
                    proposal.sent_at.isoformat()
                    if proposal.sent_at
                    else None
                ),

                "viewed_at": (
                    proposal.viewed_at.isoformat()
                    if proposal.viewed_at
                    else None
                ),

                "accepted_at": (
                    proposal.accepted_at.isoformat()
                    if proposal.accepted_at
                    else None
                ),

                "created_at": (
                    proposal.created_at.isoformat()
                ),

                "updated_at": (
                    proposal.updated_at.isoformat()
                ),
            },
        }
    )







@require_GET
@csrf_exempt
def client_proosal_api(request, public_token):
    """
    Return the complete client-facing proposal.

    React consumes this endpoint.
    """
    print(">>> CLIENT PROPOSAL API REACHED <<<")
    proposal = get_object_or_404(
        Proposal.objects.select_related(
            "lead",
            "organization",
        ),
        public_token=public_token,
    )

    # --------------------------------------------------------
    # EXPIRY
    # --------------------------------------------------------

    if (
        proposal.expires_at
        and timezone.now() > proposal.expires_at
        and proposal.status != "accepted"
    ):
        if proposal.status != "expired":
            proposal.status = "expired"
            proposal.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return JsonResponse(
            {
                "success": False,
                "error": "This proposal has expired.",
                "status": "expired",
            },
            status=410,
        )

    # --------------------------------------------------------
    # VISIBILITY
    # --------------------------------------------------------

    if proposal.status in {
        
        "cancelled",
        "rejected",
    }:
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal is not available.",
                "status": proposal.status,
            },
            status=403,
        )

    # --------------------------------------------------------
    # MARK VIEWED
    # --------------------------------------------------------

    if proposal.status == "sent": 
        proposal.status = "viewed"
        
        proposal.viewed_at = timezone.now()

        proposal.save(
            update_fields=[
                "status",
                "viewed_at",
                "updated_at",
            ]
        )

    # --------------------------------------------------------
    # RECALCULATE
    # --------------------------------------------------------

    total = recalculate_proposal_total(proposal)

    # --------------------------------------------------------
    # FEATURES
    # --------------------------------------------------------

    features = list(
        proposal.proposal_features.all().order_by(
            "sort_order",
            "created_at",
        )
    )

    required_features = [
        serialize_feature(feature)
        for feature in features
        if (
            feature.scope_status == "required"
            and feature.status == "approved"
        )
    ]

    recommended_features = [
        serialize_feature(feature)
        for feature in features
        if (
            feature.scope_status == "recommended"
            and feature.status == "approved"
        )
    ]

    optional_features = [
        serialize_feature(feature)
        for feature in features
        if (
            feature.scope_status == "optional"
            and feature.status == "approved"
        )
    ]

    # --------------------------------------------------------
    # REQUIREMENTS
    # --------------------------------------------------------

    requirements = [
        serialize_requirement(requirement)
        for requirement in proposal.requirements.all().order_by(
            "sort_order",
            "created_at",
        )
    ]

    # --------------------------------------------------------
    # SCREENS
    # --------------------------------------------------------

    screens = [
        serialize_screen(screen)
        for screen in proposal.screens.all().order_by(
            "sort_order",
            "created_at",
        )
    ]

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return JsonResponse(
        {
            "success": True,

            "proposal": {
                "id": str(proposal.id),
                "public_token": str(proposal.public_token),

                "title": proposal.title,
                "client_summary": proposal.client_summary,

                "status": proposal.status,
                "version": proposal.version,

                "client_editable": proposal.client_editable,

                "country": proposal.country,
                "currency": proposal.currency,

                "total_price": str(total),

                "formatted_total": (
                    f"{proposal.currency} "
                    f"{total:,.2f}"
                ),

                "business_objectives": (
                    proposal.business_objectives
                ),

                "confirmed_requirements": (
                    proposal.confirmed_requirements
                ),

                "recommended_requirements": (
                    proposal.recommended_requirements
                ),

                "optional_future_features": (
                    proposal.optional_future_features
                ),

                "security": proposal.security,
                "recurring_costs": proposal.recurring_costs,

                "scope": proposal.scope,
                "pages": proposal.pages,
                "features": proposal.features,

                "authentication": proposal.authentication,
                "integrations": proposal.integrations,
                "mobile": proposal.mobile,
                "backend": proposal.backend,
                "devops": proposal.devops,
                "technical_scope": proposal.technical_scope,

                "deliverables": proposal.deliverables,
                "assumptions": proposal.assumptions,
                "exclusions": proposal.exclusions,

                "timeline": proposal.timeline,
                "milestones": proposal.milestones,

                "required_features": required_features,
                "recommended_features": recommended_features,
                "optional_features": optional_features,

                "requirements": requirements,
                "screens": screens,

                "expires_at": (
                    proposal.expires_at.isoformat()
                    if proposal.expires_at
                    else None
                ),

                "accepted_version": (
                    proposal.accepted_version
                ),

                "accepted_at": (
                    proposal.accepted_at.isoformat()
                    if proposal.accepted_at
                    else None
                ),
            },
        }
    )


# ============================================================
# CLIENT FEATURE TOGGLE API
# ============================================================

@require_POST
@csrf_exempt
def client_toggle_feature_api(
    request,
    public_token,
    feature_id,
):
    """
    Toggle:

        Recommended <-> Optional
    """

    proposal = get_object_or_404(
        Proposal,
        public_token=public_token,
    )

    feature = get_object_or_404(
        ProposalFeature,
        id=feature_id,
        proposal=proposal,
    )

    # --------------------------------------------------------
    # PROPOSAL STATE
    # --------------------------------------------------------

    if proposal.status in {
        "accepted",
        "rejected",
        "expired",
        "cancelled",
    }:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal can no longer "
                    "be modified."
                ),
            },
            status=400,
        )

    # --------------------------------------------------------
    # CLIENT EDITING
    # --------------------------------------------------------

    if not proposal.client_editable:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Client editing is disabled "
                    "for this proposal."
                ),
            },
            status=403,
        )

    # --------------------------------------------------------
    # TOGGLE
    # --------------------------------------------------------

    try:

        feature, total = toggle_client_feature(
            feature
        )

    except ValueError as exc:

        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    return JsonResponse(
        {
            "success": True,

            "feature": serialize_feature(
                feature
            ),

            "proposal_total": str(total),

            "formatted_total": (
                f"{proposal.currency} "
                f"{total:,.2f}"
            ),
        }
    )


# ============================================================
# CLIENT ACCEPT API
# ============================================================
# ============================================================
# PROCUREMENT QUOTATION HELPERS
# ============================================================


def _decimal(value, default="0.00"):
    """
    Safely convert a value to Decimal.
    """
    if value is None:
        return Decimal(default)

    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def build_client_quotation_snapshot(
    quote_request,
    submitted_items=None,
):
    """
    Build the exact quotation the client is accepting.

    IMPORTANT:
        - Does NOT modify QuoteRequest.
        - Does NOT trust client prices.
        - Does NOT trust client brands/models.
        - Uses database values for prices/brand/model/etc.
        - Only quantity and inclusion can be changed by client.
        - Calculates all totals server-side.

    submitted_items format:

    [
        {
            "id": "item-uuid",
            "quantity": 10,
            "included": True,
        },
        {
            "id": "item-uuid",
            "quantity": 0,
            "included": False,
        }
    ]
    """

    db_items = list(
        quote_request.items.all()
        .order_by("created_at")
    )

    if not db_items:
        raise ValueError(
            "This quotation has no items."
        )

    # --------------------------------------------------------
    # Build lookup of real database items.
    # --------------------------------------------------------

    items_by_id = {
        str(item.id): item
        for item in db_items
    }

    # --------------------------------------------------------
    # If client did not submit changes,
    # accept all original items.
    # --------------------------------------------------------

    if submitted_items is None:

        submitted_items = [
            {
                "id": str(item.id),
                "quantity": item.quantity,
                "included": True,
            }
            for item in db_items
        ]

    if not isinstance(submitted_items, list):

        raise ValueError(
            "Quotation items must be provided as a list."
        )

    # --------------------------------------------------------
    # Track duplicate submissions.
    # --------------------------------------------------------

    submitted_ids = set()

    accepted_items = []

    subtotal = Decimal("0.00")

    # --------------------------------------------------------
    # Process client-selected items.
    # --------------------------------------------------------

    for submitted in submitted_items:

        if not isinstance(submitted, dict):
            raise ValueError(
                "Each quotation item must be an object."
            )

        raw_id = submitted.get("id")

        if not raw_id:
            raise ValueError(
                "Every quotation item must have an id."
            )

        item_id = str(raw_id)

        if item_id in submitted_ids:
            raise ValueError(
                "A quotation item was submitted more than once."
            )

        submitted_ids.add(item_id)

        # ----------------------------------------------------
        # SECURITY:
        # Client can only reference items belonging
        # to this quotation.
        # ----------------------------------------------------

        item = items_by_id.get(item_id)

        if item is None:
            raise ValueError(
                "One or more quotation items are invalid."
            )

        included = submitted.get(
            "included",
            True,
        )

        # Normalize common frontend values.
        if isinstance(included, str):
            included = included.lower() in {
                "true",
                "1",
                "yes",
                "on",
            }

        included = bool(included)

        # ----------------------------------------------------
        # Removed item.
        # ----------------------------------------------------

        if not included:
            continue

        # ----------------------------------------------------
        # Quantity.
        # ----------------------------------------------------

        raw_quantity = submitted.get(
            "quantity",
            item.quantity,
        )

        try:
            quantity = int(raw_quantity)
        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                f"Invalid quantity for {item.name}."
            )

        if quantity <= 0:
            raise ValueError(
                f"Quantity for {item.name} must be greater than zero."
            )

        # ----------------------------------------------------
        # PRICE MUST COME FROM DATABASE.
        #
        # Never accept unit_price from React.
        # ----------------------------------------------------

        if item.unit_price is None:
            raise ValueError(
                f"{item.name} does not have a unit price."
            )

        unit_price = _decimal(
            item.unit_price
        )

        line_total = (
            unit_price
            * Decimal(quantity)
        )

        subtotal += line_total

        # ----------------------------------------------------
        # Accepted item snapshot.
        #
        # Everything except quantity comes from Django.
        # ----------------------------------------------------

        accepted_items.append(
            {
                "id": str(item.id),

                "category": (
                    item.category
                    or ""
                ),

                "name": (
                    item.name
                    or ""
                ),

                "brand": (
                    item.brand
                    if item.brand
                    else None
                ),

                "model": (
                    item.model
                    if item.model
                    else None
                ),

                "description": (
                    item.description
                    or ""
                ),

                "specifications": (
                    item.specifications
                    if isinstance(
                        item.specifications,
                        dict,
                    )
                    else {}
                ),

                "quantity": quantity,

                "unit_price": str(
                    unit_price
                ),

                "total_price": str(
                    line_total
                ),
            }
        )

    # --------------------------------------------------------
    # If client removed everything, reject acceptance.
    # --------------------------------------------------------

    if not accepted_items:
        raise ValueError(
            "At least one quotation item must remain."
        )

    # --------------------------------------------------------
    # Financial values come from QuoteRequest.
    #
    # Client cannot modify these.
    # --------------------------------------------------------

    currency = (
        quote_request.currency
        or "NGN"
    )

    discount = _decimal(
        quote_request.discount
    )

    tax = _decimal(
        quote_request.tax
    )

    delivery_fee = _decimal(
        quote_request.delivery_fee
    )

    total = (
        subtotal
        - discount
        + tax
        + delivery_fee
    )

    # --------------------------------------------------------
    # Return immutable accepted quotation structure.
    # --------------------------------------------------------

    return {
        "id": str(
            quote_request.id
        ),

        "title": (
            quote_request.title
            or ""
        ),

        "request_type": (
            quote_request.request_type
            or "procurement"
        ),

        "description": (
            quote_request.description
            or ""
        ),

        "purpose": (
            quote_request.purpose
            or ""
        ),

        "notes": (
            quote_request.notes
            or ""
        ),

        "budget": (
            str(quote_request.budget)
            if quote_request.budget is not None
            else None
        ),

        "currency": currency,

        "deadline": (
            quote_request.deadline.isoformat()
            if quote_request.deadline
            else None
        ),

        "status": (
            quote_request.status
        ),

        "items": accepted_items,

        "item_count": len(
            accepted_items
        ),

        "subtotal": str(
            subtotal
        ),

        "discount": str(
            discount
        ),

        "tax": str(
            tax
        ),

        "delivery_fee": str(
            delivery_fee
        ),

        "total": str(
            total
        ),

        "formatted_subtotal": (
            f"{currency} "
            f"{subtotal:,.2f}"
        ),

        "formatted_discount": (
            f"{currency} "
            f"{discount:,.2f}"
        ),

        "formatted_tax": (
            f"{currency} "
            f"{tax:,.2f}"
        ),

        "formatted_delivery_fee": (
            f"{currency} "
            f"{delivery_fee:,.2f}"
        ),

        "formatted_total": (
            f"{currency} "
            f"{total:,.2f}"
        ),
    }


@csrf_exempt
@require_POST
@transaction.atomic
def client_accep_proposal_api(
    request,
    public_token,
):
    """
    Accept the current negotiated proposal.

    Supports:

    1. Software / service proposals
       - Uses proposal feature scope.
       - Calculates final project total.
       - Freezes accepted features.

    2. Procurement quotations
       - Uses QuoteRequest as the financial source.
       - Allows client quantity changes.
       - Allows client item removal.
       - Never trusts client-supplied prices.
       - Never trusts client-supplied brand/model.
       - Calculates final quotation server-side.
       - Freezes the exact accepted quotation.

    After acceptance:

        Proposal.status = "accepted"
        Proposal.accepted_version = current version
        Proposal.accepted_at = current time
        Proposal.client_editable = False

    The accepted quotation is stored inside:

        proposal.pricing_snapshot["accepted_scope"]["quotation"]
    """

    # ========================================================
    # GET PROPOSAL
    # ========================================================

    proposal = get_object_or_404(
        Proposal.objects
        .select_related(
            "lead",
            "organization",
            "quote_request",
        )
        .prefetch_related(
            "proposal_features",
            "quote_request__items",
        )
        .select_for_update(),
        public_token=public_token,
    )

    # ========================================================
    # STATE VALIDATION
    # ========================================================

    if proposal.status == "accepted":

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal has already "
                    "been accepted."
                ),
                "status": "accepted",
            },
            status=400,
        )

    if proposal.status in {
        "rejected",
        "expired",
        "cancelled",
    }:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal can no longer "
                    "be accepted."
                ),
                "status": proposal.status,
            },
            status=400,
        )

    # ========================================================
    # CLIENT EDITING VALIDATION
    # ========================================================

    if not proposal.client_editable:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal is no longer "
                    "available for client action."
                ),
            },
            status=403,
        )

    # ========================================================
    # EXPIRATION CHECK
    # ========================================================

    now = timezone.now()

    if (
        proposal.expires_at
        and now > proposal.expires_at
    ):

        proposal.status = "expired"

        proposal.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal has expired."
                ),
                "status": "expired",
            },
            status=410,
        )

    # ========================================================
    # READ REQUEST BODY
    # ========================================================

    data = get_client_request_data(
        request
    )

    if not isinstance(data, dict):

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Invalid request data."
                ),
            },
            status=400,
        )

    # ========================================================
    # CLIENT COMMENT
    # ========================================================

    comment = str(
        data.get(
            "comment",
            "",
        )
    ).strip()

    if len(comment) > 5000:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Your comment is too long. "
                    "Please keep it under 5000 characters."
                ),
            },
            status=400,
        )

    # ========================================================
    # DETERMINE PROCUREMENT
    # ========================================================

    quote_request = getattr(
        proposal,
        "quote_request",
        None,
    )

    is_procurement = (
        quote_request is not None
    )

    # ========================================================
    # ACCEPTED FEATURE SNAPSHOT
    # ========================================================

    accepted_features = []

    features = (
        proposal.proposal_features
        .filter(
            status="approved",
            scope_status__in=[
                "required",
                "recommended",
            ],
        )
        .order_by(
            "sort_order",
            "created_at",
        )
    )

    for feature in features:

        accepted_features.append(
            {
                "id": str(
                    feature.id
                ),

                "feature_key": (
                    feature.feature_key
                ),

                "name": (
                    feature.name
                ),

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

                "unit_price": (
                    str(
                        feature.unit_price
                    )
                    if feature.unit_price is not None
                    else None
                ),

                "total_price": (
                    str(
                        feature.total_price
                    )
                    if feature.total_price is not None
                    else None
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

                "sort_order": (
                    feature.sort_order
                ),
            }
        )

    # ========================================================
    # FINAL FINANCIAL CALCULATION
    # ========================================================

    if is_procurement:

        # ----------------------------------------------------
        # PROCUREMENT
        # ----------------------------------------------------
        #
        # IMPORTANT:
        #
        # We DO NOT call:
        #
        #     quote_request.calculate_totals()
        #
        # because that would modify the original quotation
        # using its original quantities.
        #
        # Instead we calculate the exact quotation being
        # accepted, based on:
        #
        #   database prices
        #   client quantities
        #   client inclusion/removal
        #   database discount
        #   database tax
        #   database delivery fee
        #
        # ----------------------------------------------------

        submitted_items = data.get(
            "items",
            None,
        )

        try:

            quotation_snapshot = (
                build_client_quotation_snapshot(
                    quote_request=quote_request,
                    submitted_items=submitted_items,
                )
            )

        except ValueError as exc:

            return JsonResponse(
                {
                    "success": False,
                    "error": str(exc),
                },
                status=400,
            )

        # ----------------------------------------------------
        # Final accepted quotation total.
        # ----------------------------------------------------

        total = _decimal(
            quotation_snapshot["total"]
        )

        proposal.currency = (
            quotation_snapshot["currency"]
            or proposal.currency
            or "NGN"
        )

        proposal.total_price = total

    else:

        # ----------------------------------------------------
        # NORMAL SOFTWARE / SERVICE PROPOSAL
        # ----------------------------------------------------

        total = (
            recalculate_proposal_total(
                proposal
            )
        )

        quotation_snapshot = None

    # ========================================================
    # EXISTING PRICING SNAPSHOT
    # ========================================================

    existing_snapshot = (
        proposal.pricing_snapshot
        if isinstance(
            proposal.pricing_snapshot,
            dict,
        )
        else {}
    )

    # ========================================================
    # BUILD ACCEPTED SCOPE
    # ========================================================

    accepted_scope = {
        "version": (
            proposal.version
        ),

        "currency": (
            proposal.currency
        ),

        "total": str(
            total
        ),

        "accepted_at": (
            now.isoformat()
        ),

        # ----------------------------------------------------
        # SOFTWARE / SERVICE FEATURES
        # ----------------------------------------------------

        "features": (
            accepted_features
        ),

        # ----------------------------------------------------
        # PROCUREMENT QUOTATION
        #
        # This is the EXACT quotation accepted by the client.
        # ----------------------------------------------------

        "quotation": (
            quotation_snapshot
        ),
    }

    # ========================================================
    # PRESERVE OTHER PRICING SNAPSHOT DATA
    # ========================================================

    pricing_snapshot = {
        **existing_snapshot,
        "accepted_scope": accepted_scope,
    }

    # ========================================================
    # ACCEPT PROPOSAL
    # ========================================================

    proposal.status = "accepted"

    proposal.accepted_version = (
        proposal.version
    )

    proposal.accepted_at = now

    proposal.client_editable = False

    proposal.total_price = total

    proposal.pricing_snapshot = (
        pricing_snapshot
    )

    proposal.save(
        update_fields=[
            "status",
            "accepted_version",
            "accepted_at",
            "client_editable",
            "total_price",
            "pricing_snapshot",
            "currency",
            "updated_at",
        ]
    )

    # ========================================================
    # ACCEPTANCE COMMENT
    # ========================================================

    if comment:

        ProposalComment.objects.create(
            proposal=proposal,
            message=comment,
            action="accept",
            author_type="client",
        )

    # ========================================================
    # RESPONSE
    # ========================================================

    response_data = {
        "success": True,

        "status": "accepted",

        "proposal_id": str(
            proposal.id
        ),

        "accepted_version": (
            proposal.accepted_version
        ),

        "currency": (
            proposal.currency
        ),

        "total_price": str(
            total
        ),

        "formatted_total": (
            f"{proposal.currency} "
            f"{total:,.2f}"
        ),

        "is_procurement": (
            is_procurement
        ),

        "message": (
            "Proposal accepted successfully."
        ),
    }

    # ========================================================
    # RETURN ACCEPTED QUOTATION
    # ========================================================

    if is_procurement:

        response_data[
            "quotation"
        ] = quotation_snapshot

    return JsonResponse(
        response_data,
        status=200,
    )


import secrets
import string

from django.contrib.auth import get_user_model


def generate_temporary_password(length=14):
    """
    Generate a secure temporary password.

    Uses letters, digits and symbols.
    """
    alphabet = (
        string.ascii_letters
        + string.digits
        + "!@#$%^&*()-_=+"
    )

    while True:
        password = "".join(
            secrets.choice(alphabet)
            for _ in range(length)
        )

        # Make sure the password contains all major character types.
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*()-_=+" for c in password)
        ):
            return password


def get_or_create_client_user(lead):
    """
    Find the client account using the Lead email.

    If no account exists:
    - create a CLIENT account
    - generate a temporary password
    - return the temporary password so it can be emailed

    Existing users are never given a new password.
    """

    User = get_user_model()

    email = (
        getattr(lead, "email", "") or ""
    ).strip().lower()

    if not email:
        raise ValueError(
            "The client must have an email address before "
            "accepting the proposal."
        )

    # ---------------------------------------------------------
    # FIND EXISTING ACCOUNT
    # ---------------------------------------------------------

    user = User.objects.filter(
        email__iexact=email
    ).first()

    if user:
        return user, False, None

    # ---------------------------------------------------------
    # BUILD NAME
    # ---------------------------------------------------------

    full_name = (
        getattr(lead, "name", "") or ""
    ).strip()

    name_parts = full_name.split(
        maxsplit=1
    )

    first_name = (
        name_parts[0]
        if name_parts
        else ""
    )

    last_name = (
        name_parts[1]
        if len(name_parts) > 1
        else ""
    )

    # ---------------------------------------------------------
    # GENERATE TEMPORARY PASSWORD
    # ---------------------------------------------------------

    temporary_password = (
        generate_temporary_password()
    )

    # ---------------------------------------------------------
    # CREATE CLIENT ACCOUNT
    # ---------------------------------------------------------

    user = User.objects.create_user(
        email=email,
        password=temporary_password,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.CLIENT,
    )

    # ---------------------------------------------------------
    # COPY LEAD INFORMATION
    # ---------------------------------------------------------

    if hasattr(user, "phone"):
        user.phone = (
            getattr(lead, "phone", "") or ""
        )

    if hasattr(user, "address"):
        # Only populate this if you actually have an
        # address field on Lead.
        lead_address = getattr(
            lead,
            "address",
            "",
        ) or ""

        user.address = lead_address

    user.save()

    return user, True, temporary_password









import mailchimp_transactional as Mailchimp

from django.conf import settings


import base64

import mailchimp_transactional as Mailchimp

from django.conf import settings


def send_client_account_email(
    user,
    temporary_password,
    proposal,
    pdf_file,
):
    """
    Send the newly-created client's credentials
    together with the accepted proposal PDF.
    """

    portal_url = getattr(
        settings,
        "CLIENT_PORTAL_URL",
        "http://localhost:5173/portal",
    )

    # ---------------------------------------------------------
    # READ PDF FROM MEMORY
    # ---------------------------------------------------------

    pdf_bytes = pdf_file.read()

    pdf_base64 = base64.b64encode(
        pdf_bytes
    ).decode("utf-8")

    # ---------------------------------------------------------
    # PDF FILENAME
    # ---------------------------------------------------------

    proposal_id = str(
        proposal.id
    )[:8]

    pdf_filename = (
        f"AB-Technologies-Proposal-"
        f"{proposal_id}.pdf"
    )

    # ---------------------------------------------------------
    # MAILCHIMP MESSAGE
    # ---------------------------------------------------------

    message = {
        "from_email": (
            "info@goldenprediction.com"
        ),

        "subject": (
            "Your AB Technologies Proposal "
            "Has Been Accepted"
        ),

        "text": f"""
Hello {user.first_name or "there"},

Your proposal with AB Technologies has been accepted successfully.

Your client portal account has also been created.

CLIENT PORTAL
------------------------------
Portal: {portal_url}

LOGIN DETAILS
------------------------------
Email: {user.email}
Temporary Password: {temporary_password}
------------------------------

IMPORTANT:
This is a temporary password.

Please log in to your client portal and change your password immediately.

For your security, please do not share your password with anyone.

PROPOSAL
------------------------------
{proposal.title}

Your accepted proposal is attached to this email as a PDF.

The attached document contains the final accepted project scope and pricing.

If you have any questions or need assistance, please contact AB Technologies support.

Regards,

AB Technologies
Technology. Simplified.
""",

        "to": [
            {
                "email": user.email,
                "type": "to",
            }
        ],

        # -----------------------------------------------------
        # ATTACH ACCEPTED PROPOSAL PDF
        # -----------------------------------------------------

        "attachments": [
            {
                "type": "application/pdf",
                "name": pdf_filename,
                "content": pdf_base64,
            }
        ],
    }

    client = Mailchimp.Client(
        settings.MAILCHIMP_API_KEY
    )

    return client.messages.send(
        {
            "message": message
        }
    )

from .pdf import generate_proposal_pdf











def send_accepted_proposal_email(
    user,
    proposal,
    pdf_file,
    account_created=False,
    temporary_password=None,
):
    """
    Send the accepted proposal PDF to the client.

    If `account_created` is True:
        - also include the portal URL and temporary password
          so the client can log into their new account.

    If `account_created` is False:
        - send the accepted proposal PDF only.
        - the client already has a portal account.

    This function is used by `client_accept_proposal_api`.
    """

    portal_url = getattr(
        settings,
        "CLIENT_PORTAL_URL",
        "http://localhost:5173/portal",
    )

    # ---------------------------------------------------------
    # READ PDF FROM MEMORY
    # ---------------------------------------------------------

    pdf_bytes = pdf_file.read()

    pdf_base64 = base64.b64encode(
        pdf_bytes
    ).decode("utf-8")

    # ---------------------------------------------------------
    # PDF FILENAME
    # ---------------------------------------------------------

    proposal_id = str(
        proposal.id
    )[:8]

    pdf_filename = (
        f"AB-Technologies-Proposal-"
        f"{proposal_id}.pdf"
    )

    # ---------------------------------------------------------
    # BUILD CREDENTIALS BLOCK (ONLY WHEN ACCOUNT IS NEW)
    # ---------------------------------------------------------

    if account_created and temporary_password:

        credentials_block = f"""
Your client portal account has also been created.

CLIENT PORTAL
------------------------------
Portal: {portal_url}

LOGIN DETAILS
------------------------------
Email: {user.email}
Temporary Password: {temporary_password}
------------------------------

IMPORTANT:
This is a temporary password.

Please log in to your client portal and change your password immediately.

For your security, please do not share your password with anyone.
"""

    else:

        credentials_block = f"""
You can log in to your existing client portal account
to view this accepted proposal at any time.

CLIENT PORTAL
------------------------------
Portal: {portal_url}
"""

    # ---------------------------------------------------------
    # SUBJECT
    # ---------------------------------------------------------

    if account_created:

        subject = (
            "Your AB Technologies Proposal "
            "Has Been Accepted"
        )

    else:

        subject = (
            "Your Accepted AB Technologies "
            "Proposal"
        )

    # ---------------------------------------------------------
    # MAILCHIMP MESSAGE
    # ---------------------------------------------------------

    message = {
        "from_email": (
            "info@goldenprediction.com"
        ),

        "subject": subject,

        "text": f"""
Hello {user.first_name or "there"},

Your proposal with AB Technologies has been accepted successfully.
{credentials_block}
PROPOSAL
------------------------------
{proposal.title}

Your accepted proposal is attached to this email as a PDF.

The attached document contains the final accepted project scope and pricing.

If you have any questions or need assistance, please contact AB Technologies support.

Regards,

AB Technologies
Technology. Simplified.
""",

        "to": [
            {
                "email": user.email,
                "type": "to",
            }
        ],

        # -----------------------------------------------------
        # ATTACH ACCEPTED PROPOSAL PDF
        # -----------------------------------------------------

        "attachments": [
            {
                "type": "application/pdf",
                "name": pdf_filename,
                "content": pdf_base64,
            }
        ],
    }

    client = Mailchimp.Client(
        settings.MAILCHIMP_API_KEY
    )

    return client.messages.send(
        {
            "message": message
        }
    )








@csrf_exempt
@require_POST
@transaction.atomic
def client_accept_proposal_api(
    request,
    public_token,
):

    proposal = get_object_or_404(
        Proposal.objects.select_related("lead"),
        public_token=public_token,
    )

    # ---------------------------------------------------------
    # VALIDATE PROPOSAL
    # ---------------------------------------------------------

    if proposal.status in {
        "accepted",
        "rejected",
        "expired",
        "cancelled",
    }:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal can no longer be accepted."
                ),
            },
            status=400,
        )

    if not proposal.client_editable:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal is no longer editable."
                ),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # CLIENT / LEAD
    # ---------------------------------------------------------

    lead = proposal.lead

    if not lead or not lead.email:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "A client email address is required "
                    "before this proposal can be accepted."
                ),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # CREATE / FIND CLIENT USER
    # ---------------------------------------------------------

    try:

        (
            user,
            account_created,
            temporary_password,
        ) = get_or_create_client_user(
            lead
        )

    except ValueError as exc:

        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # CALCULATE FINAL TOTAL
    # ---------------------------------------------------------

    total = recalculate_proposal_total(
        proposal
    )

    # ---------------------------------------------------------
    # ACCEPTED FEATURES
    # ---------------------------------------------------------

    accepted_features = []

    for feature in proposal.proposal_features.filter(
        status="approved",
        scope_status__in={
            "required",
            "recommended",
        },
    ):

        accepted_features.append(
            {
                "feature_key": feature.feature_key,

                "name": feature.name,

                "description": feature.description,

                "category": feature.category,

                "quantity": feature.quantity,

                "unit_price": str(
                    feature.unit_price
                ),

                "total_price": str(
                    feature.total_price
                ),

                "scope_status": (
                    feature.scope_status
                ),
            }
        )

    # ---------------------------------------------------------
    # ACCEPT PROPOSAL
    # ---------------------------------------------------------

    proposal.accepted_version = (
        proposal.version
    )

    proposal.accepted_at = (
        timezone.now()
    )

    proposal.status = "accepted"

    proposal.client_editable = False

    proposal.total_price = total

    proposal.pricing_snapshot = {
        **(
            proposal.pricing_snapshot
            or {}
        ),

        "accepted_scope": {
            "version": proposal.version,

            "features": accepted_features,

            "total_price": str(
                total
            ),
        },
    }

    proposal.save(
        update_fields=[
            "accepted_version",
            "accepted_at",
            "status",
            "client_editable",
            "total_price",
            "pricing_snapshot",
            "updated_at",
        ]
    )

    # ---------------------------------------------------------
    # ACCEPTANCE COMMENT
    # ---------------------------------------------------------

    data = get_client_request_data(
        request
    )

    comment = (
        data.get("comment") or ""
    ).strip()

    if comment:

        ProposalComment.objects.create(
            proposal=proposal,

            message=comment,

            action="accept",

            author_type="client",
        )

    # ---------------------------------------------------------
    # GENERATE ACCEPTED PROPOSAL PDF
    # ---------------------------------------------------------

    proposal_pdf = generate_proposal_pdf(
        proposal
    )

    # ---------------------------------------------------------
    # SEND EMAIL
    #
    # ALWAYS SEND THE ACCEPTED PROPOSAL PDF.
    #
    # If a new client account was created, ALSO include the
    # portal login credentials.
    #
    # Existing clients receive the accepted proposal PDF only.
    # ---------------------------------------------------------

    account_email_sent = False

    try:

        send_accepted_proposal_email(
            user=user,

            proposal=proposal,

            pdf_file=proposal_pdf,

            account_created=(
                account_created
            ),

            temporary_password=(
                temporary_password
                if account_created
                else None
            ),
        )

        account_email_sent = True

    except Exception as exc:

        raise RuntimeError(
            "The proposal was accepted, but "
            "the client email could not be sent."
        ) from exc

    # ---------------------------------------------------------
    # RESPONSE MESSAGE
    # ---------------------------------------------------------

    if account_created:

        message = (
            "Proposal accepted successfully. "
            "Your client portal account has been created. "
            "Your login details and accepted proposal "
            "have been sent to your email."
        )

    else:

        message = (
            "Proposal accepted successfully. "
            "Your accepted proposal has been sent "
            "to your email."
        )

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    return JsonResponse(
        {
            "success": True,

            "status": "accepted",

            "proposal_id": str(
                proposal.id
            ),

            "accepted_version": (
                proposal.accepted_version
            ),

            "total_price": str(
                total
            ),

            "client": {
                "user_id": str(
                    user.id
                ),

                "name": (
                    getattr(
                        proposal.lead,
                        "name",
                        "",
                    )
                    or ""
                ),

                "email": user.email,

                "account_created": (
                    account_created
                ),

                "account_email_sent": (
                    account_email_sent
                ),
            },

            "message": message,

            "redirect_url": "/portal",
        }
    )





















@csrf_exempt
@require_POST
@transaction.atomic
def client_accept_pro_api(
    request,
    public_token,
):

    proposal = get_object_or_404(
        Proposal.objects.select_related("lead"),
        public_token=public_token,
    )

    # ---------------------------------------------------------
    # VALIDATE PROPOSAL
    # ---------------------------------------------------------

    if proposal.status in {
        "accepted",
        "rejected",
        "expired",
        "cancelled",
    }:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal can no longer be accepted."
                ),
            },
            status=400,
        )

    if not proposal.client_editable:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This proposal is no longer editable."
                ),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # CLIENT / LEAD
    # ---------------------------------------------------------

    lead = proposal.lead

    if not lead or not lead.email:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "A client email address is required "
                    "before this proposal can be accepted."
                ),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # CREATE / FIND CLIENT USER
    # ---------------------------------------------------------

    try:

        (
            user,
            account_created,
            temporary_password,
        ) = get_or_create_client_user(
            lead
        )

    except ValueError as exc:

        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # CALCULATE FINAL TOTAL
    # ---------------------------------------------------------

    total = recalculate_proposal_total(
        proposal
    )

    # ---------------------------------------------------------
    # ACCEPTED FEATURES
    # ---------------------------------------------------------

    accepted_features = []

    for feature in proposal.proposal_features.filter(
        status="approved",
        scope_status__in={
            "required",
            "recommended",
        },
    ):

        accepted_features.append(
            {
                "feature_key": feature.feature_key,

                "name": feature.name,

                "description": feature.description,

                "category": feature.category,

                "quantity": feature.quantity,

                "unit_price": str(
                    feature.unit_price
                ),

                "total_price": str(
                    feature.total_price
                ),

                "scope_status": (
                    feature.scope_status
                ),
            }
        )

    # ---------------------------------------------------------
    # ACCEPT PROPOSAL
    # ---------------------------------------------------------

    proposal.accepted_version = (
        proposal.version
    )

    proposal.accepted_at = (
        timezone.now()
    )

    proposal.status = "accepted"

    proposal.client_editable = False

    proposal.total_price = total

    proposal.pricing_snapshot = {
        **(
            proposal.pricing_snapshot
            or {}
        ),

        "accepted_scope": {
            "version": proposal.version,

            "features": accepted_features,

            "total_price": str(
                total
            ),
        },
    }

    proposal.save(
        update_fields=[
            "accepted_version",
            "accepted_at",
            "status",
            "client_editable",
            "total_price",
            "pricing_snapshot",
            "updated_at",
        ]
    )

    # ---------------------------------------------------------
    # ACCEPTANCE COMMENT
    # ---------------------------------------------------------

    data = get_client_request_data(
        request
    )

    comment = (
        data.get("comment") or ""
    ).strip()

    if comment:

        ProposalComment.objects.create(
            proposal=proposal,

            message=comment,

            action="accept",

            author_type="client",
        )

    # ---------------------------------------------------------
    # GENERATE ACCEPTED PROPOSAL PDF
    # ---------------------------------------------------------

    proposal_pdf = generate_proposal_pdf(
        proposal
    )

    # ---------------------------------------------------------
    # SEND EMAIL
    #
    # ONLY NEW ACCOUNTS RECEIVE LOGIN CREDENTIALS.
    #
    # Existing clients do not receive a new password.
    # ---------------------------------------------------------

    account_email_sent = False

    if account_created:

        try:

            send_client_account_email(
                user=user,

                temporary_password=(
                    temporary_password
                ),

                proposal=proposal,

                pdf_file=proposal_pdf,
            )

            account_email_sent = True

        except Exception as exc:

            raise RuntimeError(
                "The proposal was accepted, but "
                "the client account email could not "
                "be sent."
            ) from exc

    # ---------------------------------------------------------
    # RESPONSE MESSAGE
    # ---------------------------------------------------------

    if account_created:

        message = (
            "Proposal accepted successfully. "
            "Your client portal account has been created. "
            "Your login details and accepted proposal "
            "have been sent to your email."
        )

    else:

        message = (
            "Proposal accepted successfully. "
            "Your accepted proposal has been sent "
            "to your email."
        )

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    return JsonResponse(
        {
            "success": True,

            "status": "accepted",

            "proposal_id": str(
                proposal.id
            ),

            "accepted_version": (
                proposal.accepted_version
            ),

            "total_price": str(
                total
            ),

            "client": {
                "user_id": str(
                    user.id
                ),

                "name": (
                    getattr(
                        proposal.lead,
                        "name",
                        "",
                    )
                    or ""
                ),

                "email": user.email,

                "account_created": (
                    account_created
                ),

                "account_email_sent": (
                    account_email_sent
                ),
            },

            "message": message,

            "redirect_url": "/portal",
        }
    )















@csrf_exempt
@require_POST
def client_api(request, public_token):
    proposal = get_object_or_404(
        Proposal.objects.select_related("lead", "organization"),
        public_token=public_token,
    )

    # -----------------------------------------
    # Validate proposal state
    # -----------------------------------------

    if proposal.status == "accepted":
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal has already been accepted.",
                "status": "accepted",
            },
            status=400,
        )

    if proposal.status in {
        "rejected",
        "expired",
        "cancelled",
    }:
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal can no longer be accepted.",
                "status": proposal.status,
            },
            status=400,
        )

    if not proposal.client_editable:
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal is no longer available for client action.",
            },
            status=403,
        )

    # -----------------------------------------
    # Check expiration
    # -----------------------------------------

    if (
        proposal.expires_at
        and timezone.now() > proposal.expires_at
    ):
        proposal.status = "expired"
        proposal.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return JsonResponse(
            {
                "success": False,
                "error": "This proposal has expired.",
                "status": "expired",
            },
            status=410,
        )

    # -----------------------------------------
    # Read client comment
    # -----------------------------------------

    data = get_client_request_data(request)

    comment = str(
        data.get("comment", "")
    ).strip()

    # -----------------------------------------
    # Recalculate FINAL price
    # -----------------------------------------

    total = recalculate_proposal_total(proposal)

    # -----------------------------------------
    # Save accepted scope snapshot
    # -----------------------------------------

    accepted_features = []

    features = proposal.proposal_features.filter(
        status="approved",
        scope_status__in=[
            "required",
            "recommended",
        ],
    )

    for feature in features:
        accepted_features.append(
            {
                "id": str(feature.id),
                "feature_key": feature.feature_key,
                "name": feature.name,
                "description": feature.description,
                "category": feature.category,
                "complexity": feature.complexity,
                "quantity": feature.quantity,
                "unit_price": str(feature.unit_price),
                "total_price": str(feature.total_price),
                "scope_status": feature.scope_status,
            }
        )

    # Preserve any existing pricing snapshot.
    pricing_snapshot = proposal.pricing_snapshot or {}

    pricing_snapshot["accepted_scope"] = {
        "version": proposal.version,
        "currency": proposal.currency,
        "total": str(total),
        "accepted_at": timezone.now().isoformat(),
        "features": accepted_features,
    }

    # -----------------------------------------
    # Update proposal
    # -----------------------------------------

    now = timezone.now()

    proposal.status = "accepted"
    proposal.accepted_version = proposal.version
    proposal.accepted_at = now
    proposal.client_editable = False
    proposal.total_price = total
    proposal.pricing_snapshot = pricing_snapshot

    proposal.save(
        update_fields=[
            "status",
            "accepted_version",
            "accepted_at",
            "client_editable",
            "total_price",
            "pricing_snapshot",
            "updated_at",
        ]
    )

    # -----------------------------------------
    # Save client acceptance comment
    # -----------------------------------------

    if comment:
        ProposalComment.objects.create(
            proposal=proposal,
            message=comment,
            action="accept",
            author_type="client",
        )

    return JsonResponse(
        {
            "success": True,
            "status": "accepted",
            "proposal_id": str(proposal.id),
            "accepted_version": proposal.accepted_version,
            "total_price": str(total),
            "formatted_total": (
                f"{proposal.currency} {total:,.2f}"
            ),
            "message": (
                "Proposal accepted successfully."
            ),
        }
    )













@csrf_exempt
@require_POST
def client_decline_proposal_api(request, public_token):
    proposal = get_object_or_404(
        Proposal.objects.select_related(
            "lead",
            "organization",
        ),
        public_token=public_token,
    )

    # -----------------------------------------
    # Validate state
    # -----------------------------------------

    if proposal.status == "rejected":
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal has already been declined.",
                "status": "rejected",
            },
            status=400,
        )

    if proposal.status == "accepted":
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal has already been accepted.",
                "status": "accepted",
            },
            status=400,
        )

    if proposal.status in {
        "expired",
        "cancelled",
    }:
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal can no longer be declined.",
                "status": proposal.status,
            },
            status=400,
        )

    if not proposal.client_editable:
        return JsonResponse(
            {
                "success": False,
                "error": "This proposal is no longer available for client action.",
            },
            status=403,
        )

    # -----------------------------------------
    # Check expiration
    # -----------------------------------------

    if (
        proposal.expires_at
        and timezone.now() > proposal.expires_at
    ):
        proposal.status = "expired"

        proposal.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return JsonResponse(
            {
                "success": False,
                "error": "This proposal has expired.",
                "status": "expired",
            },
            status=410,
        )

    # -----------------------------------------
    # Read comment
    # -----------------------------------------

    data = get_client_request_data(request)

    comment = str(
        data.get("comment", "")
    ).strip()

    # -----------------------------------------
    # Decline reason is required
    # -----------------------------------------

    if len(comment) < 5:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Please provide a brief reason "
                    "for declining the proposal."
                ),
            },
            status=400,
        )

    if len(comment) > 5000:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Your comment is too long. "
                    "Please keep it under 5000 characters."
                ),
            },
            status=400,
        )

    # -----------------------------------------
    # Reject proposal
    # -----------------------------------------

    now = timezone.now()

    proposal.status = "rejected"
    proposal.rejected_at = now
    proposal.client_editable = False

    proposal.save(
        update_fields=[
            "status",
            "rejected_at",
            "client_editable",
            "updated_at",
        ]
    )

    # -----------------------------------------
    # Save client response
    # -----------------------------------------

    ProposalComment.objects.create(
        proposal=proposal,
        message=comment,
        action="decline",
        author_type="client",
    )

    return JsonResponse(
    {
        "success": True,
        "status": "rejected",
        "proposal_id": str(proposal.id),
        "message": (
            "Proposal declined successfully. "
            "Our support team is available if you would like to discuss "
            "changes or request a revision."
        ),
        "redirect_url": "/support",
    }
)





from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction

from rest_framework.response import Response
from rest_framework import status

from .models import Proposal

def calculate_client_quotation(
    quote_request,
    changes,
):
    """
    Calculate the client's final quotation.

    Client may:
        - change quantity
        - include/exclude an existing item

    Client may NOT:
        - change unit price
        - change brand
        - change model
        - change specifications

    The original QuoteRequest is never modified.
    """

    original_items = {
        str(item.id): item
        for item in quote_request.items.all()
    }

    requested_items = changes.get(
        "items",
        [],
    )

    if not isinstance(
        requested_items,
        list,
    ):
        raise ValueError(
            "items must be a list."
        )

    selected_items = []

    seen_item_ids = set()

    for change in requested_items:

        if not isinstance(
            change,
            dict,
        ):
            raise ValueError(
                "Each quotation item must be an object."
            )

        item_id = str(
            change.get("id", "")
        ).strip()

        if not item_id:
            raise ValueError(
                "Each quotation item must have an id."
            )

        # -----------------------------------------------------
        # DUPLICATES
        # -----------------------------------------------------

        if item_id in seen_item_ids:
            raise ValueError(
                f"Quotation item {item_id} was submitted more than once."
            )

        seen_item_ids.add(item_id)

        # -----------------------------------------------------
        # FIND ORIGINAL ITEM
        # -----------------------------------------------------

        item = original_items.get(
            item_id
        )

        if item is None:
            raise ValueError(
                "One or more quotation items are invalid."
            )

        # -----------------------------------------------------
        # INCLUDED
        # -----------------------------------------------------

        included = change.get(
            "included",
            True,
        )

        if not isinstance(
            included,
            bool,
        ):
            raise ValueError(
                f"Invalid included value for {item.name}."
            )

        # Client removed this item.
        if not included:
            continue

        # -----------------------------------------------------
        # QUANTITY
        # -----------------------------------------------------

        try:

            quantity = int(
                change.get(
                    "quantity",
                    item.quantity,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            raise ValueError(
                f"Invalid quantity for {item.name}."
            )

        if quantity < 1:

            raise ValueError(
                f"Quantity for {item.name} "
                "must be at least 1."
            )

        if quantity > 100000:

            raise ValueError(
                f"Quantity for {item.name} "
                "is too large."
            )

        # -----------------------------------------------------
        # PRICE MUST EXIST
        # -----------------------------------------------------

        if item.unit_price is None:

            raise ValueError(
                f"{item.name} does not have "
                "a confirmed unit price."
            )

        # -----------------------------------------------------
        # CALCULATE LINE TOTAL
        # -----------------------------------------------------

        unit_price = Decimal(
            item.unit_price
        )

        total_price = (
            unit_price * quantity
        )

        selected_items.append(
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

                "quantity": quantity,

                "unit_price": str(
                    unit_price
                ),

                "total_price": str(
                    total_price
                ),
            }
        )

    # ---------------------------------------------------------
    # MUST KEEP AT LEAST ONE ITEM
    # ---------------------------------------------------------

    if not selected_items:

        raise ValueError(
            "At least one quotation item must remain."
        )

    # ---------------------------------------------------------
    # SUBTOTAL
    # ---------------------------------------------------------

    subtotal = sum(
        (
            Decimal(
                item["total_price"]
            )
            for item in selected_items
        ),
        Decimal("0.00"),
    )

    # ---------------------------------------------------------
    # OTHER FINANCIAL VALUES
    #
    # These remain controlled by Django.
    # ---------------------------------------------------------

    discount = (
        quote_request.discount
        or Decimal("0.00")
    )

    tax = (
        quote_request.tax
        or Decimal("0.00")
    )

    delivery_fee = (
        quote_request.delivery_fee
        or Decimal("0.00")
    )

    total = (
        subtotal
        - discount
        + tax
        + delivery_fee
    )

    currency = (
        quote_request.currency
        or "NGN"
    )

    # ---------------------------------------------------------
    # RETURN FROZEN QUOTATION DATA
    # ---------------------------------------------------------

    return {
        "id": str(
            quote_request.id
        ),

        "title": quote_request.title,

        "request_type": (
            quote_request.request_type
        ),

        "description": (
            quote_request.description
        ),

        "purpose": (
            quote_request.purpose
        ),

        "notes": (
            quote_request.notes
        ),

        "currency": currency,

        "items": selected_items,

        "item_count": len(
            selected_items
        ),

        "subtotal": str(
            subtotal
        ),

        "discount": str(
            discount
        ),

        "tax": str(
            tax
        ),

        "delivery_fee": str(
            delivery_fee
        ),

        "total": str(
            total
        ),

        "formatted_subtotal": (
            f"{currency} "
            f"{subtotal:,.2f}"
        ),

        "formatted_discount": (
            f"{currency} "
            f"{discount:,.2f}"
        ),

        "formatted_tax": (
            f"{currency} "
            f"{tax:,.2f}"
        ),

        "formatted_delivery_fee": (
            f"{currency} "
            f"{delivery_fee:,.2f}"
        ),

        "formatted_total": (
            f"{currency} "
            f"{total:,.2f}"
        ),
    }




@csrf_exempt
@require_POST
@transaction.atomic
def client_quote_preview_api(request, public_token):
    proposal = get_object_or_404(
        Proposal.objects
        .select_related(
            "lead",
            "organization",
            "quote_request",
        )
        .prefetch_related(
            "quote_request__items",
        ),
        public_token=public_token,
    )

    if proposal.status in {
        "rejected",
        "expired",
        "cancelled",
        "completed",
    }:
        return Response(
            {
                "detail": "This proposal can no longer be modified."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    quote_request = getattr(proposal, "quote_request", None)

    if not quote_request:
        return Response(
            {
                "detail": "This proposal does not contain a quotation."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if proposal.status == "accepted":
        return Response(
            {
                "detail": "This quotation has already been accepted."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        import json

        if request.content_type == "application/json":
            data = json.loads(
                request.body.decode("utf-8") or "{}"
            )
        else:
            data = request.POST.dict()

        quotation = calculate_client_quotation(
            quote_request,
            data,
        )

    except ValueError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception:
        return Response(
            {
                "detail": "Unable to calculate quotation."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({
        "success": True,
        "quotation": quotation,
    })



# proposals/views.py

from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Proposal


class ClientQuotationPreviewView(APIView):
    """
    Preview a client-edited procurement quotation without modifying
    the original QuoteRequest.

    The client can:
    - change quantity
    - remove an item

    The client cannot:
    - change unit price
    - change brand
    - change model
    - change specifications

    Django remains the source of truth for all pricing.
    """

    permission_classes = [AllowAny]

    def post(self, request, public_token):

        proposal = get_object_or_404(
            Proposal.objects
            .select_related("quote_request")
            .prefetch_related("quote_request__items"),
            public_token=public_token,
        )

        # ---------------------------------------------------------
        # VALIDATE PROPOSAL STATE
        # ---------------------------------------------------------

        if proposal.status in {
            "accepted",
            "rejected",
            "expired",
            "cancelled",
        }:
            return Response(
                {
                    "success": False,
                    "error": (
                        "This quotation can no longer be modified."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not proposal.client_editable:
            return Response(
                {
                    "success": False,
                    "error": (
                        "This quotation is not available for client editing."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        quotation = getattr(
            proposal,
            "quote_request",
            None,
        )

        if quotation is None:
            return Response(
                {
                    "success": False,
                    "error": "This proposal does not contain a quotation.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # REQUEST DATA
        # ---------------------------------------------------------

        payload = request.data

        if not isinstance(payload, dict):
            return Response(
                {
                    "success": False,
                    "error": "Invalid quotation data.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        submitted_items = payload.get("items", [])

        if not isinstance(submitted_items, list):
            return Response(
                {
                    "success": False,
                    "error": "Items must be provided as a list.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # ORIGINAL DJANGO ITEMS
        # ---------------------------------------------------------

        original_items = {
            str(item.id): item
            for item in quotation.items.all()
        }

        # ---------------------------------------------------------
        # BUILD CLIENT SELECTION
        # ---------------------------------------------------------

        selected_items = []

        seen_item_ids = set()

        for submitted in submitted_items:

            if not isinstance(submitted, dict):
                return Response(
                    {
                        "success": False,
                        "error": "Invalid quotation item.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            item_id = str(
                submitted.get("id", "")
            ).strip()

            if not item_id:
                return Response(
                    {
                        "success": False,
                        "error": "Quotation item ID is required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if item_id in seen_item_ids:
                return Response(
                    {
                        "success": False,
                        "error": (
                            f"Quotation item {item_id} was submitted "
                            "more than once."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            seen_item_ids.add(item_id)

            original_item = original_items.get(item_id)

            if original_item is None:
                return Response(
                    {
                        "success": False,
                        "error": (
                            "One or more quotation items are invalid."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # -----------------------------------------------------
            # INCLUDED
            # -----------------------------------------------------

            included = submitted.get(
                "included",
                True,
            )

            if not isinstance(included, bool):
                return Response(
                    {
                        "success": False,
                        "error": (
                            "The included value must be true or false."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Removed items are simply skipped.
            if not included:
                continue

            # -----------------------------------------------------
            # QUANTITY
            # -----------------------------------------------------

            quantity = submitted.get(
                "quantity",
                original_item.quantity,
            )

            try:
                quantity = int(quantity)
            except (
                TypeError,
                ValueError,
            ):
                return Response(
                    {
                        "success": False,
                        "error": (
                            f"Invalid quantity for "
                            f"{original_item.name}."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if quantity < 1:
                return Response(
                    {
                        "success": False,
                        "error": (
                            f"Quantity for {original_item.name} "
                            "must be at least 1. "
                            "Use included=false to remove the item."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # -----------------------------------------------------
            # UNIT PRICE ALWAYS COMES FROM DJANGO
            # -----------------------------------------------------

            if original_item.unit_price is None:
                return Response(
                    {
                        "success": False,
                        "error": (
                            f"{original_item.name} does not have "
                            "a confirmed unit price."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unit_price = Decimal(
                original_item.unit_price
            )

            total_price = (
                unit_price *
                quantity
            )

            selected_items.append(
                {
                    "id": item_id,
                    "category": original_item.category,
                    "name": original_item.name,
                    "brand": original_item.brand,
                    "model": original_item.model,
                    "description": original_item.description,
                    "specifications": (
                        original_item.specifications
                        if isinstance(
                            original_item.specifications,
                            dict,
                        )
                        else {}
                    ),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                }
            )

        # ---------------------------------------------------------
        # REQUIRE AT LEAST ONE ITEM
        # ---------------------------------------------------------

        if not selected_items:
            return Response(
                {
                    "success": False,
                    "error": (
                        "At least one quotation item must remain."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # CALCULATE TOTAL
        # ---------------------------------------------------------

        subtotal = sum(
            (
                item["total_price"]
                for item in selected_items
            ),
            Decimal("0.00"),
        )

        discount = Decimal(
            quotation.discount or 0
        )

        tax = Decimal(
            quotation.tax or 0
        )

        delivery_fee = Decimal(
            quotation.delivery_fee or 0
        )

        total = (
            subtotal
            - discount
            + tax
            + delivery_fee
        )

        currency = (
            quotation.currency
            or proposal.currency
            or "NGN"
        )

        # ---------------------------------------------------------
        # RESPONSE ITEMS
        # ---------------------------------------------------------

        serialized_items = []

        for item in selected_items:

            serialized_items.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "name": item["name"],
                    "brand": item["brand"],
                    "model": item["model"],
                    "description": item["description"],
                    "specifications": item["specifications"],
                    "quantity": item["quantity"],
                    "unit_price": str(
                        item["unit_price"]
                    ),
                    "total_price": str(
                        item["total_price"]
                    ),
                }
            )

        # ---------------------------------------------------------
        # RESPONSE
        # ---------------------------------------------------------

        return Response(
            {
                "success": True,
                "quotation": {
                    "id": str(quotation.id),
                    "title": quotation.title,
                    "request_type": quotation.request_type,
                    "description": quotation.description,
                    "purpose": quotation.purpose,
                    "notes": quotation.notes,
                    "currency": currency,
                    "deadline": (
                        quotation.deadline.isoformat()
                        if quotation.deadline
                        else None
                    ),
                    "budget": (
                        str(quotation.budget)
                        if quotation.budget is not None
                        else None
                    ),
                    "status": quotation.status,

                    "items": serialized_items,

                    "item_count": len(
                        serialized_items
                    ),

                    "subtotal": str(
                        subtotal
                    ),

                    "discount": str(
                        discount
                    ),

                    "tax": str(
                        tax
                    ),

                    "delivery_fee": str(
                        delivery_fee
                    ),

                    "total": str(
                        total
                    ),

                    "formatted_subtotal": (
                        f"{currency} "
                        f"{subtotal:,.2f}"
                    ),

                    "formatted_discount": (
                        f"{currency} "
                        f"{discount:,.2f}"
                    ),

                    "formatted_tax": (
                        f"{currency} "
                        f"{tax:,.2f}"
                    ),

                    "formatted_delivery_fee": (
                        f"{currency} "
                        f"{delivery_fee:,.2f}"
                    ),

                    "formatted_total": (
                        f"{currency} "
                        f"{total:,.2f}"
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )
    












from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST




def _serialize_saved_quotation(quote):
    items = []

    for item in quote.items.all().order_by("created_at"):
        items.append({
            "id": str(item.id),
            "category": item.category,
            "name": item.name,
            "brand": item.brand,
            "model": item.model,
            "description": item.description,
            "specifications": (
                item.specifications
                if isinstance(item.specifications, dict)
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
        })

    currency = quote.currency or "NGN"

    return {
        "id": str(quote.id),
        "title": quote.title,
        "request_type": quote.request_type,
        "description": quote.description,
        "purpose": quote.purpose,
        "notes": quote.notes,
        "budget": (
            str(quote.budget)
            if quote.budget is not None
            else None
        ),
        "currency": currency,
        "deadline": (
            quote.deadline.isoformat()
            if quote.deadline
            else None
        ),
        "status": quote.status,
        "items": items,
        "item_count": len(items),
        "subtotal": str(quote.subtotal),
        "discount": str(quote.discount),
        "tax": str(quote.tax),
        "delivery_fee": str(quote.delivery_fee),
        "total": str(quote.total),
        "formatted_subtotal": f"{currency} {quote.subtotal:,.2f}",
        "formatted_discount": f"{currency} {quote.discount:,.2f}",
        "formatted_tax": f"{currency} {quote.tax:,.2f}",
        "formatted_delivery_fee": f"{currency} {quote.delivery_fee:,.2f}",
        "formatted_total": f"{currency} {quote.total:,.2f}",
    }


@csrf_exempt
@require_POST
def client_update_quotation(request, public_token):
    """
    Permanently update the client's quotation selections.

    React sends:
    {
        "items": [
            {
                "id": "item-uuid",
                "quantity": 10,
                "included": true
            },
            {
                "id": "item-uuid",
                "quantity": 0,
                "included": false
            }
        ]
    }

    Django remains the source of truth for prices.
    """

    try:
        proposal = (
            Proposal.objects
            .select_related("quote_request", "lead")
            .get(public_token=public_token)
        )
    except Proposal.DoesNotExist:
        return JsonResponse(
            {"detail": "Proposal not found."},
            status=404,
        )

    # ---------------------------------------------------------
    # BASIC PROPOSAL VALIDATION
    # ---------------------------------------------------------

    if proposal.status in {"accepted", "rejected", "expired", "completed"}:
        return JsonResponse(
            {
                "detail": (
                    "This proposal can no longer be edited."
                )
            },
            status=403,
        )

    if not getattr(proposal, "client_editable", False):
        return JsonResponse(
            {
                "detail": (
                    "This proposal is no longer editable."
                )
            },
            status=403,
        )

    quote = getattr(proposal, "quote_request", None)

    if not quote:
        return JsonResponse(
            {
                "detail": (
                    "This proposal does not contain a quotation."
                )
            },
            status=400,
        )

    # ---------------------------------------------------------
    # PARSE JSON
    # ---------------------------------------------------------

    try:
        import json

        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"detail": "Invalid JSON request."},
            status=400,
        )

    submitted_items = payload.get("items")

    if not isinstance(submitted_items, list):
        return JsonResponse(
            {
                "detail": (
                    "items must be a list."
                )
            },
            status=400,
        )

    # ---------------------------------------------------------
    # GET ORIGINAL DB ITEMS
    # ---------------------------------------------------------

    db_items = list(
        quote.items
        .select_for_update()
        .order_by("created_at")
    )

    if not db_items:
        return JsonResponse(
            {
                "detail": (
                    "This quotation has no items."
                )
            },
            status=400,
        )

    item_map = {
        str(item.id): item
        for item in db_items
    }

    # ---------------------------------------------------------
    # VALIDATE SUBMITTED ITEMS
    # ---------------------------------------------------------

    changes = {}
    seen_ids = set()

    for raw_item in submitted_items:

        if not isinstance(raw_item, dict):
            return JsonResponse(
                {
                    "detail": (
                        "Each quotation item must be an object."
                    )
                },
                status=400,
            )

        item_id = str(
            raw_item.get("id", "")
        ).strip()

        if not item_id:
            return JsonResponse(
                {
                    "detail": (
                        "Every quotation item requires an id."
                    )
                },
                status=400,
            )

        if item_id in seen_ids:
            return JsonResponse(
                {
                    "detail": (
                        f"Duplicate quotation item: {item_id}"
                    )
                },
                status=400,
            )

        seen_ids.add(item_id)

        if item_id not in item_map:
            return JsonResponse(
                {
                    "detail": (
                        "One or more quotation items "
                        "do not belong to this quotation."
                    )
                },
                status=400,
            )

        item = item_map[item_id]

        # -----------------------------------------------------
        # INCLUDED
        # -----------------------------------------------------

        included = raw_item.get(
            "included",
            True,
        )

        if not isinstance(included, bool):
            return JsonResponse(
                {
                    "detail": (
                        f"Invalid included value for "
                        f"{item.name}."
                    )
                },
                status=400,
            )

        # -----------------------------------------------------
        # QUANTITY
        # -----------------------------------------------------

        quantity = raw_item.get(
            "quantity",
            item.quantity,
        )

        if isinstance(quantity, bool):
            return JsonResponse(
                {
                    "detail": (
                        f"Invalid quantity for {item.name}."
                    )
                },
                status=400,
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "detail": (
                        f"Quantity for {item.name} "
                        "must be a whole number."
                    )
                },
                status=400,
            )

        if quantity < 0:
            return JsonResponse(
                {
                    "detail": (
                        f"Quantity for {item.name} "
                        "cannot be negative."
                    )
                },
                status=400,
            )

        if included and quantity <= 0:
            return JsonResponse(
                {
                    "detail": (
                        f"Quantity for {item.name} "
                        "must be greater than zero."
                    )
                },
                status=400,
            )

        changes[item_id] = {
            "included": included,
            "quantity": quantity,
        }

    # ---------------------------------------------------------
    # UPDATE DATABASE
    # ---------------------------------------------------------

    try:
        with transaction.atomic():

            # Re-fetch quotation under lock.
            quote = (
                quote.__class__
                .objects
                .select_for_update()
                .get(pk=quote.pk)
            )

            # Re-fetch items.
            db_items = list(
                quote.items
                .select_for_update()
                .order_by("created_at")
            )

            item_map = {
                str(item.id): item
                for item in db_items
            }

            subtotal = Decimal("0.00")
            included_count = 0

            for item in db_items:

                item_id = str(item.id)

                # If React did not send this item,
                # leave its current database quantity unchanged.
                change = changes.get(item_id)

                if change is None:
                    included = item.quantity > 0
                    quantity = item.quantity
                else:
                    included = change["included"]
                    quantity = change["quantity"]

                # -------------------------------------------------
                # REMOVED ITEM
                # -------------------------------------------------

                if not included:

                    item.quantity = 0
                    item.total_price = Decimal("0.00")

                    item.save(
                        update_fields=[
                            "quantity",
                            "total_price",
                            "updated_at",
                        ]
                    )

                    continue

                # -------------------------------------------------
                # INCLUDED ITEM
                # -------------------------------------------------

                if item.unit_price is None:
                    raise ValueError(
                        f"{item.name} does not have a unit price."
                    )

                item.quantity = quantity

                item.total_price = (
                    item.unit_price * quantity
                )

                item.save(
                    update_fields=[
                        "quantity",
                        "total_price",
                        "updated_at",
                    ]
                )

                subtotal += item.total_price
                included_count += 1

            if included_count == 0:
                raise ValueError(
                    "At least one quotation item must be included."
                )

            # -------------------------------------------------
            # CALCULATE FINAL QUOTATION TOTAL
            # -------------------------------------------------

            discount = (
                quote.discount
                if quote.discount is not None
                else Decimal("0.00")
            )

            tax = (
                quote.tax
                if quote.tax is not None
                else Decimal("0.00")
            )

            delivery_fee = (
                quote.delivery_fee
                if quote.delivery_fee is not None
                else Decimal("0.00")
            )

            total = (
                subtotal
                - discount
                + tax
                + delivery_fee
            )

            if total < Decimal("0.00"):
                total = Decimal("0.00")

            quote.subtotal = subtotal
            quote.total = total

            # A quotation with prices is now priced.
            quote.status = "priced"

            quote.save(
                update_fields=[
                    "subtotal",
                    "total",
                    "status",
                    "updated_at",
                ]
            )

            # -------------------------------------------------
            # IMPORTANT:
            # Proposal total must ALSO change.
            # -------------------------------------------------

            proposal.total_price = total
            proposal.currency = (
                quote.currency or "NGN"
            )

            proposal.save(
                update_fields=[
                    "total_price",
                    "currency",
                    "updated_at",
                ]
            )

    except ValueError as exc:
        return JsonResponse(
            {
                "detail": str(exc),
            },
            status=400,
        )

    # ---------------------------------------------------------
    # RETURN ACTUAL SAVED DATABASE VALUES
    # ---------------------------------------------------------

    quote.refresh_from_db()

    return JsonResponse(
        {
            "success": True,
            "message": (
                "Quotation updated successfully."
            ),
            "quotation": _serialize_saved_quotation(
                quote
            ),
            "total_price": str(
                proposal.total_price
            ),
            "formatted_total": (
                f"{quote.currency or 'NGN'} "
                f"{quote.total:,.2f}"
            ),
        },
        status=200,
    )





from decimal import Decimal

from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import Proposal
from crm.models import ProcurementQuotationItem


class ClientProcurementListView(APIView):
    """
    Return procurement quotations belonging to the logged-in client.

    Procurement is identified by:

        Proposal.source == "quote_request"

    The related QuoteRequest is the authoritative quotation source.

    Only accepted/completed procurement proposals are returned.
    """

    permission_classes = [IsAuthenticated]

    PROJECT_STATUSES = {
        "accepted",
        "completed",
    }

    PROCUREMENT_SOURCE = "quote_request"

    def get_client_email(self, request):
        """
        The existing proposal system associates proposals with Lead,
        and Lead contains the client's email.

        The logged-in account email is therefore used to locate the
        client's procurement proposals.
        """
        return (
            str(getattr(request.user, "email", "") or "")
            .strip()
            .lower()
        )

    def decimal_string(self, value):
        if value is None:
            return None

        return str(value)

    def serialize_item(self, item):
        return {
            "id": str(item.id),
            "category": item.category,
            "name": item.name,
            "brand": item.brand,
            "model": item.model,
            "description": item.description,
            "specifications": item.specifications,
            "quantity": item.quantity,
            "unit_price": self.decimal_string(
                item.unit_price
            ),
            "total_price": self.decimal_string(
                item.total_price
            ),
            "included": item.quantity > 0,
        }

    def serialize_procurement(self, proposal):
        quote = proposal.quote_request

        items = list(
            quote.items.all().order_by(
                "created_at",
                "id",
            )
        )

        included_items = [
            item
            for item in items
            if item.quantity > 0
        ]

        total_quantity = sum(
            item.quantity
            for item in included_items
        )

        return {
            "id": str(proposal.id),

            "public_token": str(
                proposal.public_token
            ),

            "title": (
                proposal.title
                or quote.title
                or "Procurement Request"
            ),

            "source": proposal.source,

            "status": proposal.status,

            "version": proposal.version,

            "accepted_version": (
                proposal.accepted_version
            ),

            "client_editable": bool(
                proposal.client_editable
            ),

            "quote_request_id": (
                str(quote.id)
                if quote
                else None
            ),

            "request_type": (
                quote.request_type
                if quote
                else None
            ),

            "description": (
                quote.description
                if quote
                else ""
            ),

            "purpose": (
                quote.purpose
                if quote
                else ""
            ),

            "notes": (
                quote.notes
                if quote
                else ""
            ),

            "budget": self.decimal_string(
                quote.budget
                if quote
                else None
            ),

            "currency": (
                quote.currency
                if quote
                else proposal.currency
            ),

            "deadline": (
                quote.deadline.isoformat()
                if quote and quote.deadline
                else None
            ),

            "subtotal": self.decimal_string(
                quote.subtotal
                if quote
                else None
            ),

            "discount": self.decimal_string(
                quote.discount
                if quote
                else None
            ),

            "tax": self.decimal_string(
                quote.tax
                if quote
                else None
            ),

            "delivery_fee": self.decimal_string(
                quote.delivery_fee
                if quote
                else None
            ),

            "total": self.decimal_string(
                quote.total
                if quote
                else proposal.total_price
            ),

            "formatted_total": (
                proposal.formatted_price
            ),

            "item_count": len(included_items),

            "total_quantity": total_quantity,

            "items": [
                self.serialize_item(item)
                for item in items
            ],

            "created_at": (
                proposal.created_at.isoformat()
                if proposal.created_at
                else None
            ),

            "updated_at": (
                proposal.updated_at.isoformat()
                if proposal.updated_at
                else None
            ),

            "sent_at": (
                proposal.sent_at.isoformat()
                if proposal.sent_at
                else None
            ),

            "viewed_at": (
                proposal.viewed_at.isoformat()
                if proposal.viewed_at
                else None
            ),

            "accepted_at": (
                proposal.accepted_at.isoformat()
                if proposal.accepted_at
                else None
            ),

            "rejected_at": (
                proposal.rejected_at.isoformat()
                if proposal.rejected_at
                else None
            ),
        }

    def get(self, request, format=None):
        client_email = self.get_client_email(request)

        if not client_email:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Your account does not have "
                        "an email address."
                    ),
                },
                status=400,
            )

        proposals = (
            Proposal.objects
            .filter(
                source=self.PROCUREMENT_SOURCE,
                status__in=self.PROJECT_STATUSES,
                quote_request__isnull=False,
                lead__email__iexact=client_email,
            )
            .select_related(
                "lead",
                "quote_request",
            )
            .prefetch_related(
                Prefetch(
                    "quote_request__items",
                    queryset=(
                        ProcurementQuotationItem.objects
                        .all()
                        .order_by(
                            "created_at",
                            "id",
                        )
                    ),
                )
            )
            .order_by(
                "-updated_at",
                "-created_at",
            )
        )

        procurement = [
            self.serialize_procurement(
                proposal
            )
            for proposal in proposals
        ]

        return Response(
            {
                "success": True,
                "count": len(procurement),
                "procurement": procurement,
            }
        )
    


from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import Proposal

from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import Proposal


class ClientProcurementDetailView(APIView):
    """
    Return one procurement quotation for the authenticated client.

    Procurement is authoritative by:

        Proposal.source == "quote_request"

    The permanent procurement tracking reference belongs to the
    QuoteRequest itself.

    Example:

        AB-TRK-7F3A91C2D8

    The tracking reference belongs to the procurement, not to
    individual tracking updates.
    """

    permission_classes = [IsAuthenticated]

    PROCUREMENT_SOURCE = "quote_request"

    ALLOWED_STATUSES = {
        "accepted",
        "completed",
    }

    # ============================================================
    # SERIALIZERS
    # ============================================================

    def serialize_item(self, item):
        """
        Serialize one procurement quotation item.

        Django remains the source of truth for all financial values.
        """

        return {
            "id": str(item.id),

            "category": item.category,

            "name": item.name,

            "brand": item.brand,

            "model": item.model,

            "description": item.description,

            "specifications": item.specifications,

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

            "included": item.quantity > 0,
        }

    # ============================================================
    # GET
    # ============================================================

    def get(self, request, public_token, format=None):

        # --------------------------------------------------------
        # AUTHENTICATED CLIENT EMAIL
        # --------------------------------------------------------

        client_email = (
            str(
                getattr(
                    request.user,
                    "email",
                    "",
                )
                or ""
            )
            .strip()
            .lower()
        )

        if not client_email:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Your account does not have "
                        "an email address."
                    ),
                },
                status=400,
            )

        # --------------------------------------------------------
        # FIND PROCUREMENT
        # --------------------------------------------------------

        proposal = get_object_or_404(
            Proposal.objects
            .select_related(
                "lead",
                "organization",
                "quote_request",
            )
            .prefetch_related(
                "quote_request__items",
            ),
            public_token=public_token,
            source=self.PROCUREMENT_SOURCE,
            status__in=self.ALLOWED_STATUSES,
            quote_request__isnull=False,
            lead__email__iexact=client_email,
        )

        quote = proposal.quote_request

        # --------------------------------------------------------
        # ITEMS
        # --------------------------------------------------------

        items = list(
            quote.items.all().order_by(
                "created_at",
                "id",
            )
        )

        serialized_items = [
            self.serialize_item(item)
            for item in items
        ]

        included_items = [
            item
            for item in items
            if item.quantity > 0
        ]

        total_quantity = sum(
            item.quantity
            for item in included_items
        )

        # --------------------------------------------------------
        # TRACKING REFERENCE
        # --------------------------------------------------------
        #
        # IMPORTANT:
        #
        # The tracking reference belongs to QuoteRequest.
        #
        # It is NOT generated per tracking update.
        #
        # Example:
        #
        # AB-TRK-7F3A91C2D8
        #
        # Every tracking update for this procurement uses
        # the same reference.
        # --------------------------------------------------------

        tracking_reference = (
            quote.tracking_reference
            or None
        )

        # --------------------------------------------------------
        # QUOTATION
        # --------------------------------------------------------

        quotation = {
            "id": str(quote.id),

            "tracking_reference": tracking_reference,

            "title": quote.title,

            "request_type": quote.request_type,

            "description": quote.description,

            "purpose": quote.purpose,

            "notes": quote.notes,

            "budget": (
                str(quote.budget)
                if quote.budget is not None
                else None
            ),

            "currency": quote.currency,

            "deadline": (
                quote.deadline.isoformat()
                if quote.deadline
                else None
            ),

            "status": quote.status,

            "items": serialized_items,

            "item_count": len(
                included_items
            ),

            "total_quantity": total_quantity,

            "subtotal": (
                str(quote.subtotal)
                if quote.subtotal is not None
                else None
            ),

            "discount": (
                str(quote.discount)
                if quote.discount is not None
                else None
            ),

            "tax": (
                str(quote.tax)
                if quote.tax is not None
                else None
            ),

            "delivery_fee": (
                str(quote.delivery_fee)
                if quote.delivery_fee is not None
                else None
            ),

            "total": (
                str(quote.total)
                if quote.total is not None
                else None
            ),

            "formatted_total": (
                proposal.formatted_price
            ),

            "created_at": (
                quote.created_at.isoformat()
                if quote.created_at
                else None
            ),

            "updated_at": (
                quote.updated_at.isoformat()
                if quote.updated_at
                else None
            ),
        }

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

        return Response(
            {
                "success": True,

                "procurement": {
                    "id": str(proposal.id),

                    "public_token": str(
                        proposal.public_token
                    ),

                    "title": (
                        proposal.title
                        or quote.title
                        or "Procurement"
                    ),

                    "source": proposal.source,

                    "status": proposal.status,

                    "version": proposal.version,

                    "accepted_version": (
                        proposal.accepted_version
                    ),

                    "client_editable": bool(
                        proposal.client_editable
                    ),

                    "organization": (
                        proposal.organization.name
                        if proposal.organization
                        else None
                    ),

                    # ------------------------------------------------
                    # IMPORTANT:
                    # Expose the permanent tracking reference
                    # directly on procurement.
                    # ------------------------------------------------

                    "tracking_reference": tracking_reference,

                    # ------------------------------------------------
                    # QUOTATION
                    # ------------------------------------------------

                    "quotation": quotation,

                    # ------------------------------------------------
                    # PROPOSAL DATES
                    # ------------------------------------------------

                    "created_at": (
                        proposal.created_at.isoformat()
                        if proposal.created_at
                        else None
                    ),

                    "updated_at": (
                        proposal.updated_at.isoformat()
                        if proposal.updated_at
                        else None
                    ),

                    "sent_at": (
                        proposal.sent_at.isoformat()
                        if proposal.sent_at
                        else None
                    ),

                    "viewed_at": (
                        proposal.viewed_at.isoformat()
                        if proposal.viewed_at
                        else None
                    ),

                    "accepted_at": (
                        proposal.accepted_at.isoformat()
                        if proposal.accepted_at
                        else None
                    ),

                    "rejected_at": (
                        proposal.rejected_at.isoformat()
                        if proposal.rejected_at
                        else None
                    ),
                },
            }
        )
    






from django.shortcuts import get_object_or_404

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.models import QuoteRequest


class PublicProcurementTrackingView(APIView):
    """
    Public procurement tracking.

    A client can enter their permanent procurement tracking
    reference and view the current procurement status/history.

    Example:

        AB-TRK-7F3A91C2D8
    """

    permission_classes = [AllowAny]

    def serialize_item(self, item):
        return {
            "id": str(item.id),
            "category": item.category,
            "name": item.name,
            "brand": item.brand,
            "model": item.model,
            "description": item.description,
            "specifications": item.specifications,
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
            "included": item.quantity > 0,
        }

    def serialize_update(self, update):
        return {
            "id": str(update.id),

            "status": update.status,

            "status_label": update.get_status_display(),

            "title": update.title,

            "description": (
                update.description or ""
            ),

            "location": (
                update.location or ""
            ),

            "tracking_reference": (
                update.quotation.tracking_reference
            ),

            "updated_by": (
                getattr(
                    update.updated_by,
                    "full_name",
                    None,
                )
                or getattr(
                    update.updated_by,
                    "email",
                    None,
                )
                if update.updated_by
                else None
            ),

            "created_at": (
                update.created_at.isoformat()
                if update.created_at
                else None
            ),
        }

    def get(
        self,
        request,
        tracking_reference,
        format=None,
    ):
        # --------------------------------------------------------
        # NORMALIZE REFERENCE
        # --------------------------------------------------------

        tracking_reference = (
            str(tracking_reference or "")
            .strip()
            .upper()
        )

        if not tracking_reference:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Please provide a tracking reference."
                    ),
                },
                status=400,
            )

        # --------------------------------------------------------
        # FIND QUOTATION
        # --------------------------------------------------------

        quote = get_object_or_404(
            QuoteRequest.objects
            .prefetch_related(
                "items",
                "tracking_updates",
                "tracking_updates__updated_by",
            ),
            tracking_reference=tracking_reference,
        )

        # --------------------------------------------------------
        # ITEMS
        # --------------------------------------------------------

        items = list(
            quote.items.all().order_by(
                "created_at",
                "id",
            )
        )

        included_items = [
            item
            for item in items
            if item.quantity > 0
        ]

        serialized_items = [
            self.serialize_item(item)
            for item in items
        ]

        total_quantity = sum(
            item.quantity
            for item in included_items
        )

        # --------------------------------------------------------
        # TRACKING HISTORY
        # --------------------------------------------------------

        updates = list(
            quote.tracking_updates
            .select_related(
                "updated_by",
            )
            .order_by(
                "-created_at",
            )
        )

        tracking = [
            self.serialize_update(update)
            for update in updates
        ]

        latest_tracking = (
            tracking[0]
            if tracking
            else None
        )

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

        return Response(
            {
                "success": True,

                "procurement": {
                    "id": str(quote.id),

                    "tracking_reference": (
                        quote.tracking_reference
                    ),

                    "title": quote.title,

                    "request_type": (
                        quote.request_type
                    ),

                    "description": (
                        quote.description
                        or ""
                    ),

                    "purpose": (
                        quote.purpose
                        or ""
                    ),

                    "notes": (
                        quote.notes
                        or ""
                    ),

                    "currency": (
                        quote.currency
                    ),

                    "deadline": (
                        quote.deadline.isoformat()
                        if quote.deadline
                        else None
                    ),

                    "status": quote.status,

                    "status_label": (
                        quote.get_status_display()
                    ),

                    "items": serialized_items,

                    "item_count": len(
                        included_items
                    ),

                    "total_quantity": (
                        total_quantity
                    ),

                    "subtotal": (
                        str(quote.subtotal)
                        if quote.subtotal is not None
                        else None
                    ),

                    "discount": (
                        str(quote.discount)
                        if quote.discount is not None
                        else None
                    ),

                    "tax": (
                        str(quote.tax)
                        if quote.tax is not None
                        else None
                    ),

                    "delivery_fee": (
                        str(quote.delivery_fee)
                        if quote.delivery_fee is not None
                        else None
                    ),

                    "total": (
                        str(quote.total)
                        if quote.total is not None
                        else None
                    ),

                    "formatted_total": (
                        quote.formatted_total
                    ),

                    "tracking_count": (
                        len(tracking)
                    ),

                    "current_tracking_status": (
                        latest_tracking["status"]
                        if latest_tracking
                        else None
                    ),

                    "current_tracking_status_label": (
                        latest_tracking["status_label"]
                        if latest_tracking
                        else None
                    ),

                    "latest_tracking": (
                        latest_tracking
                    ),

                    "tracking": tracking,

                    "created_at": (
                        quote.created_at.isoformat()
                        if quote.created_at
                        else None
                    ),

                    "updated_at": (
                        quote.updated_at.isoformat()
                        if quote.updated_at
                        else None
                    ),
                },
            }
        )
