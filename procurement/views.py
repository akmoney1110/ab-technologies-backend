from django.shortcuts import render

# Create your views here.
 # procurement/views.py

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.models import QuoteRequest
from proposals.models import Proposal

from .models import ProcurementTrackingUpdate


class IsStaffOrAdmin(IsAuthenticated):
    """
    Replace this with your existing IsStaffOrAdmin
    if you already have it.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        user = request.user

        return (
            user.is_superuser
            or user.is_staff
            or getattr(user, "role", None)
            in {"ADMIN", "MANAGER", "STAFF"}
        )


class StaffProcurementTrackingView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def get_procurement(self, proposal_id):
        return get_object_or_404(
            Proposal.objects.select_related(
                "quote_request",
                "lead",
                "organization",
            ),
            id=proposal_id,
            source="quote_request",
            quote_request__isnull=False,
            status__in=["accepted", "completed"],
        )

    def serialize_update(self, update):
        return {
            "id": update.id,
            "status": update.status,
            "status_label": update.get_status_display(),
            "title": update.title,
            "description": update.description,
            "location": update.location,
            "tracking_reference": update.tracking_reference,
            "updated_by": (
                update.updated_by.get_full_name()
                or update.updated_by.email
                if update.updated_by
                else None
            ),
            "created_at": update.created_at.isoformat(),
        }

    def get(self, request, proposal_id):
        proposal = self.get_procurement(proposal_id)

        quote = proposal.quote_request

        updates = quote.tracking_updates.select_related(
            "updated_by"
        ).all()

        return Response({
            "success": True,
            "procurement": {
                "id": str(proposal.id),
                "title": (
                    proposal.title
                    or quote.title
                    or "Procurement"
                ),
                "proposal_status": proposal.status,
                "quote_id": str(quote.id),
                "client": (
                    quote.lead.name
                    if quote.lead
                    else None
                ),
                "tracking": [
                    self.serialize_update(update)
                    for update in updates
                ],
            },
        })

    @transaction.atomic
    def post(self, request, proposal_id):
        proposal = self.get_procurement(proposal_id)

        quote = proposal.quote_request

        status_value = str(
            request.data.get("status", "")
        ).strip()

        title = str(
            request.data.get("title", "")
        ).strip()

        description = str(
            request.data.get("description", "")
        ).strip()

        location = str(
            request.data.get("location", "")
        ).strip()

        tracking_reference = str(
            request.data.get("tracking_reference", "")
        ).strip()

        valid_statuses = {
            choice[0]
            for choice in ProcurementTrackingUpdate.STATUS_CHOICES
        }

        if status_value not in valid_statuses:
            return Response(
                {
                    "success": False,
                    "error": "Invalid tracking status.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not title:
            return Response(
                {
                    "success": False,
                    "error": "Tracking update title is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        update = ProcurementTrackingUpdate.objects.create(
            quotation=quote,
            status=status_value,
            title=title,
            description=description,
            location=location,
            
            updated_by=request.user,
        )

        return Response(
            {
                "success": True,
                "message": "Procurement tracking updated.",
                "tracking": self.serialize_update(update),
            },
            status=status.HTTP_201_CREATED,
        )
    


# procurement/views.py

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import Proposal

from .models import ProcurementTrackingUpdate


# ============================================================
# PERMISSIONS
# ============================================================

class IsStaffOrAdmin(IsAuthenticated):
    """
    Staff / admin access control.

    Replace with your existing IsStaffOrAdmin
    if you already have one.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        user = request.user

        return (
            user.is_superuser
            or user.is_staff
            or getattr(user, "role", None)
            in {"ADMIN", "MANAGER", "STAFF"}
        )


# ============================================================
# HELPERS
# ============================================================

def _decimal_str(value):
    """
    Serialize a Decimal safely.
    """
    if value is None:
        return None
    return str(value)


def serialize_quotation_item(item):
    """
    Serialize a single procurement quotation item.

    Mirrors the shape returned by the client proposal API
    so the staff UI can reuse the same renderers.
    """
    quantity = int(item.quantity or 0)

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

        "quantity": quantity,

        "included": quantity > 0,

        "unit_price": _decimal_str(item.unit_price),

        "total_price": _decimal_str(item.total_price),
    }


def serialize_quotation(quote):
    """
    Serialize the full QuoteRequest attached to a procurement
    Proposal, including authoritative pricing from Django.
    """
    if quote is None:
        return None

    items = [
        serialize_quotation_item(item)
        for item in quote.items.all().order_by("created_at")
    ]

    included_items = [
        item for item in items if item["included"]
    ]

    removed_items = [
        item for item in items if not item["included"]
    ]

    total_quantity = sum(
        item["quantity"] for item in included_items
    )

    currency = quote.currency or "NGN"

    return {
        "id": str(quote.id),

        "title": quote.title,

        "request_type": quote.request_type,

        "description": quote.description,

        "purpose": quote.purpose,

        "notes": quote.notes,

        "budget": _decimal_str(quote.budget),

        "currency": currency,

        "deadline": (
            quote.deadline.isoformat()
            if quote.deadline
            else None
        ),

        "status": quote.status,

        "items": items,

        "included_items": included_items,

        "removed_items": removed_items,

        "item_count": len(included_items),

        "total_item_count": len(items),

        "total_quantity": total_quantity,

        "subtotal": _decimal_str(quote.subtotal),

        "discount": _decimal_str(quote.discount),

        "tax": _decimal_str(quote.tax),

        "delivery_fee": _decimal_str(quote.delivery_fee),

        "total": _decimal_str(quote.total),

        "formatted_subtotal": (
            f"{currency} {quote.subtotal:,.2f}"
            if quote.subtotal is not None
            else None
        ),

        "formatted_discount": (
            f"{currency} {quote.discount:,.2f}"
            if quote.discount is not None
            else None
        ),

        "formatted_tax": (
            f"{currency} {quote.tax:,.2f}"
            if quote.tax is not None
            else None
        ),

        "formatted_delivery_fee": (
            f"{currency} {quote.delivery_fee:,.2f}"
            if quote.delivery_fee is not None
            else None
        ),

        "formatted_total": (
            f"{currency} {quote.total:,.2f}"
            if quote.total is not None
            else None
        ),
    }


def serialize_tracking_update(update):
    """
    Serialize a single procurement tracking update.
    """
    user = update.updated_by

    if user:
        try:
            updated_by = (
                user.get_full_name() or user.email
            )
        except Exception:
            updated_by = getattr(user, "email", None)
    else:
        updated_by = None

    return {
        "id": update.id,

        "status": update.status,

        "status_label": update.get_status_display(),

        "title": update.title,

        "description": update.description,

        "location": update.location,

        "tracking_reference": (
    update.quotation.tracking_reference
    if update.quotation
    else None
),

        "updated_by": updated_by,

        "created_at": (
            update.created_at.isoformat()
            if update.created_at
            else None
        ),
    }


def serialize_procurement_proposal(proposal, include_tracking=False):
    """
    Serialize a procurement Proposal.

    Used by both the list endpoint and the detail endpoint.
    """
    quote = getattr(proposal, "quote_request", None)

    quotation = serialize_quotation(quote)

    tracking = []

    if include_tracking and quote is not None:
        tracking = [
            serialize_tracking_update(update)
            for update in (
                quote.tracking_updates
                .select_related("updated_by")
                .order_by("-created_at")
            )
        ]

    # Latest tracking status (for the list view).
    latest_status = None
    latest_status_label = None

    if quote is not None:
        latest = (
            quote.tracking_updates
            .order_by("-created_at")
            .first()
        )

        if latest is not None:
            latest_status = latest.status
            latest_status_label = latest.get_status_display()

    return {
        "id": str(proposal.id),

        "proposal_id": str(proposal.id),

        "procurement_code": (
            f"PROC-{str(proposal.id)[:8].upper()}"
        ),

        "title": proposal.title,

        "name": proposal.title,

        "type": "procurement",

        "business_type": "procurement",

        "source": proposal.source,

        "status": proposal.status,

        "version": proposal.version,

        "currency": proposal.currency,

        "total_price": _decimal_str(
            proposal.total_price
        ),

        "accepted_at": (
            proposal.accepted_at.isoformat()
            if proposal.accepted_at
            else None
        ),

        "completed_at": (
            proposal.completed_at.isoformat()
            if getattr(
                proposal,
                "completed_at",
                None,
            )
            else None
        ),

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

        "client": (
            str(proposal.lead)
            if proposal.lead
            else None
        ),

        "lead_name": (
            proposal.lead.name
            if proposal.lead
            else None
        ),

        "lead_email": (
            proposal.lead.email
            if proposal.lead
            else None
        ),

        "is_active": proposal.status == "accepted",

        "is_completed": proposal.status == "completed",

        "quotation": quotation,

        "latest_tracking_status": latest_status,

        "latest_tracking_status_label": (
            latest_status_label
        ),

        "tracking": tracking,
    }


def get_procurement_proposal(proposal_id):
    """
    Fetch a procurement proposal that is either accepted or
    completed and has a linked QuoteRequest.

    Returns the Proposal or raises Http404.
    """
    return get_object_or_404(
        Proposal.objects
        .select_related(
            "quote_request",
            "lead",
            "organization",
        )
        .prefetch_related(
            "quote_request__items",
            "quote_request__tracking_updates",
            "quote_request__tracking_updates__updated_by",
        ),
        id=proposal_id,
        source="quote_request",
        quote_request__isnull=False,
        status__in=["accepted", "completed"],
    )


# ============================================================
# STAFF PROCUREMENT LIST
# ============================================================

class StaffProcurementListView(APIView):
    """
    GET /api/procurement/staff/

    Returns every accepted/completed procurement proposal
    linked to a QuoteRequest.
    """
    permission_classes = [IsStaffOrAdmin]

    def get(self, request):
        proposals = (
            Proposal.objects
            .filter(
                source="quote_request",
                quote_request__isnull=False,
                status__in=["accepted", "completed"],
            )
            .select_related(
                "quote_request",
                "lead",
                "organization",
            )
            .prefetch_related(
                "quote_request__items",
                "quote_request__tracking_updates",
                "quote_request__tracking_updates__updated_by",
            )
            .order_by("-updated_at")
        )

        data = [
            serialize_procurement_proposal(
                proposal,
                include_tracking=False,
            )
            for proposal in proposals
        ]

        return Response(data, status=status.HTTP_200_OK)


# ============================================================
# STAFF PROCUREMENT DETAIL
# ============================================================

class StaffProcurementDetailView(APIView):
    """
    GET /api/procurement/staff/<proposal_id>/

    Full procurement detail including quotation items and
    complete tracking history.
    """
    permission_classes = [IsStaffOrAdmin]

    def get(self, request, proposal_id):
        proposal = get_procurement_proposal(proposal_id)

        data = serialize_procurement_proposal(
            proposal,
            include_tracking=True,
        )

        return Response(data, status=status.HTTP_200_OK)


# ============================================================
# STAFF PROCUREMENT TRACKING (LIST + CREATE)
# ============================================================

class StaffProcurementTrackingView(APIView):
    """
    GET  /api/procurement/staff/<proposal_id>/tracking/
         List tracking updates.

    POST /api/procurement/staff/<proposal_id>/tracking/
         Create a new tracking update.
    """
    permission_classes = [IsStaffOrAdmin]

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def get(self, request, proposal_id):
        proposal = get_procurement_proposal(proposal_id)

        quote = proposal.quote_request

        updates = (
            quote.tracking_updates
            .select_related("updated_by")
            .order_by("-created_at")
        )

        return Response(
            {
                "success": True,

                "procurement": {
                    "id": str(proposal.id),

                    "title": (
                        proposal.title
                        or quote.title
                        or "Procurement"
                    ),

                    "proposal_status": (
                        proposal.status
                    ),

                    "quote_id": str(quote.id),

                    "client": (
                        quote.lead.name
                        if quote.lead
                        else None
                    ),

                    "tracking": [
                        serialize_tracking_update(update)
                        for update in updates
                    ],
                },
            },
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    @transaction.atomic
    def post(self, request, proposal_id):
        proposal = get_procurement_proposal(proposal_id)

        quote = proposal.quote_request

        status_value = str(
            request.data.get("status", "")
        ).strip().lower()

        title = str(
            request.data.get("title", "")
        ).strip()

        description = str(
            request.data.get("description", "")
        ).strip()

        location = str(
            request.data.get("location", "")
        ).strip()

        tracking_reference = str(
            request.data.get("tracking_reference", "")
        ).strip()

        valid_statuses = {
            choice[0]
            for choice in ProcurementTrackingUpdate.STATUS_CHOICES
        }

        if status_value not in valid_statuses:
            return Response(
                {
                    "success": False,
                    "error": "Invalid tracking status.",
                    "allowed_statuses": sorted(
                        valid_statuses
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not title:
            return Response(
                {
                    "success": False,
                    "error": (
                        "Tracking update title is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        update = ProcurementTrackingUpdate.objects.create(
            quotation=quote,
            status=status_value,
            title=title,
            description=description,
            location=location,
            
            updated_by=request.user,
        )

        return Response(
            {
                "success": True,

                "message": (
                    "Procurement tracking updated."
                ),

                "tracking": serialize_tracking_update(
                    update
                ),

                "procurement": {
                    "id": str(proposal.id),

                    "title": (
                        proposal.title
                        or quote.title
                        or "Procurement"
                    ),

                    "proposal_status": (
                        proposal.status
                    ),

                    "quote_id": str(quote.id),

                    "client": (
                        quote.lead.name
                        if quote.lead
                        else None
                    ),

                    "latest_tracking_status": (
                        update.status
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# OPTIONAL: MARK PROCUREMENT COMPLETED
# ============================================================

class StaffProcurementCompleteView(APIView):
    """
    POST /api/procurement/staff/<proposal_id>/complete/

    Marks the procurement proposal as completed.

    Requires the latest tracking update to be in a
    terminal state ("delivered" or "completed"), if you
    have such statuses in ProcurementTrackingUpdate.
    """
    permission_classes = [IsStaffOrAdmin]

    @transaction.atomic
    def post(self, request, proposal_id):
        proposal = get_procurement_proposal(proposal_id)

        if proposal.status == "completed":
            return Response(
                {
                    "success": True,
                    "message": (
                        "Procurement is already completed."
                    ),
                    "procurement": (
                        serialize_procurement_proposal(
                            proposal,
                            include_tracking=False,
                        )
                    ),
                },
                status=status.HTTP_200_OK,
            )

        proposal.status = "completed"
        proposal.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,
                "message": "Procurement completed.",
                "procurement": (
                    serialize_procurement_proposal(
                        proposal,
                        include_tracking=False,
                    )
                ),
            },
            status=status.HTTP_200_OK,
        )
















# procurement/views.py

from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
# procurement/views.py

from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from proposals.models import Proposal
from procurement.models import ProcurementTrackingUpdate


class ClientProcurementTrackingView(APIView):
    """
    Client-facing procurement tracking endpoint.

    Allows an authenticated client to view the tracking timeline
    for their own accepted/completed procurement quotation.

    GET:
        /api/procurement/client/<public_token>/tracking/
    """

    permission_classes = [IsAuthenticated]

    PROCUREMENT_SOURCE = "quote_request"

    PROCUREMENT_STATUSES = [
        "accepted",
        "completed",
    ]

    def get_procurement(self, request, public_token):
        """
        Return the procurement proposal belonging to the
        authenticated client.
        """

        client_email = str(
            getattr(request.user, "email", "") or ""
        ).strip().lower()

        if not client_email:
            return None

        proposal = get_object_or_404(
            Proposal.objects
            .select_related(
                "lead",
                "organization",
                "quote_request",
            )
            .prefetch_related(
                "quote_request__tracking_updates",
                "quote_request__tracking_updates__updated_by",
            ),
            public_token=public_token,
            source=self.PROCUREMENT_SOURCE,
            status__in=self.PROCUREMENT_STATUSES,
            quote_request__isnull=False,
            lead__email__iexact=client_email,
        )

        return proposal

    def serialize_tracking_update(self, update):
        updated_by = None

        if update.updated_by:
            updated_by = (
            getattr(update.updated_by, "full_name", None)
            or getattr(update.updated_by, "email", None)
            or str(update.updated_by)
        )

        return {
        "id": str(update.id),

        "status": update.status,

        "status_label": update.get_status_display(),

        "title": update.title,

        "description": update.description or "",

        "location": update.location or "",

        "tracking_reference": (
    update.quotation.tracking_reference
    if update.quotation
    else None
),

        "updated_by": updated_by,

        "created_at": (
            update.created_at.isoformat()
            if update.created_at
            else None
        ),
    }

    def get(self, request, public_token, format=None):
        """
        Return the complete procurement tracking timeline
        for the authenticated client.
        """

        client_email = str(
            getattr(request.user, "email", "") or ""
        ).strip().lower()

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

        proposal = self.get_procurement(
            request,
            public_token,
        )

        quote = proposal.quote_request

        # Get tracking updates belonging to this quotation.
        updates = list(
            quote.tracking_updates
            .select_related("updated_by")
            .order_by("-created_at")
        )

        tracking = [
            self.serialize_tracking_update(update)
            for update in updates
        ]

        latest_tracking = (
            tracking[0]
            if tracking
            else None
        )

        return Response(
            {
                "success": True,

                "procurement": {
                    # Proposal information
                    "id": str(proposal.id),

                    "public_token": str(
                        proposal.public_token
                    ),

                    "title": (
                        proposal.title
                        or quote.title
                        or "Procurement"
                    ),

                    "proposal_status": (
                        proposal.status
                    ),

                    # Quote information
                    "quote_id": str(
                        quote.id
                    ),

                    "quote_title": (
                        quote.title
                        or ""
                    ),

                    "quote_status": (
                        quote.status
                    ),

                    # Tracking information
                    "tracking_count": len(
                        tracking
                    ),

                    "current_tracking_status": (
                        latest_tracking["status"]
                        if latest_tracking
                        else None
                    ),

                    "current_tracking_status_label": (
                        latest_tracking[
                            "status_label"
                        ]
                        if latest_tracking
                        else None
                    ),

                    "latest_tracking": (
                        latest_tracking
                    ),

                    "tracking": tracking,
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

