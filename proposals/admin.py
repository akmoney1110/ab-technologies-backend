from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.conf import settings
from proposals.services import (
    generate_initial_proposal,
    
)
from .models import (
    PricingRule,
    Proposal,
    ProposalRevision,ProposalScreen
)


# =========================================================
# HELPERS
# =========================================================
from django.contrib import admin
from .models import Proposal, ProposalMilestone

class ProposalMilestoneInline(admin.TabularInline):
    model = ProposalMilestone
    extra = 1
    fields = (
        "order", "title", "description",
        "amount", "percentage",
        "payment_required", "status", "payment_status",
        "due_date",
    )

def display_value(value, fallback="Not specified"):
    """
    Convert common AI JSON values into something readable.
    """

    if value is None:
        return fallback

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, str):
        return value.strip() or fallback

    return value


def normalize_item(item):
    """
    Convert AI-generated list items into a predictable structure.

    Supports:
        "Authentication"
        {"name": "..."}
        {"title": "..."}
        {"label": "..."}
        {"page": "..."}
        {"feature": "..."}
        {"type": "..."}
    """

    if isinstance(item, str):
        return {
            "name": item,
            "description": "",
            "raw": item,
        }

    if isinstance(item, dict):

        name = (
            item.get("name")
            or item.get("title")
            or item.get("label")
            or item.get("page")
            or item.get("feature")
            or item.get("type")
            or "Item"
        )

        description = (
            item.get("description")
            or item.get("summary")
            or item.get("details")
            or item.get("purpose")
            or ""
        )

        return {
            "name": str(name),
            "description": str(description),
            "raw": item,
        }

    return {
        "name": str(item),
        "description": "",
        "raw": item,
    }

class ProposalScreenInline(admin.TabularInline):
    model = ProposalScreen
    extra = 1

    fields = (
        "name",
        "screen_type",
        "complexity",
        "status",
        "sort_order",
    )

    ordering = (
        "sort_order",
        "created_at",
    )

    show_change_link = True



def normalize_list(value):
    """
    Normalize an AI-generated list.
    """

    if not isinstance(value, list):
        return []

    return [
        normalize_item(item)
        for item in value
    ]


def normalize_dict(value):
    """
    Guarantee a dictionary.
    """

    if isinstance(value, dict):
        return value

    return {}


def pretty_json(value):
    """
    Pretty-print JSON for internal review.
    """

    import json

    try:
        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return str(value)

import os
def get_frontend_url():
    """
    Get the frontend application URL.
    """

    return getattr(
        settings,
        frontend_url = settings.FRONTEND_URL)



def get_client_proposal_url(proposal, request=None):
    """
    Generate the React client proposal URL.
    """

    if not proposal:
        return "-"

    frontend_url = get_frontend_url()

    return f"{frontend_url}/proposals/{proposal.public_token}"

# =========================================================
# PRICING RULE ADMIN
# =========================================================

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "code",
        "category",
        "region",
        "currency",
        "unit",
        "price",
        "is_active",
        "priority",
        "updated_at",
    )

    list_filter = (
        "category",
        "region",
        "currency",
        "unit",
        "is_active",
    )

    search_fields = (
        "name",
        "code",
        "description",
    )

    ordering = (
        "category",
        "-priority",
        "name",
    )

    list_editable = (
        "price",
        "is_active",
        "priority",
    )

    fieldsets = (

        # -------------------------------------------------
        # RULE
        # -------------------------------------------------

        (
            "Pricing Rule",
            {
                "fields": (
                    "name",
                    "code",
                    "description",
                )
            },
        ),

        # -------------------------------------------------
        # PRICING
        # -------------------------------------------------

        (
            "Pricing",
            {
                "fields": (
                    "category",
                    "region",
                    "currency",
                    "unit",
                    "price",
                )
            },
        ),

        # -------------------------------------------------
        # CONTROL
        # -------------------------------------------------

        (
            "Control",
            {
                "fields": (
                    "is_active",
                    "priority",
                )
            },
        ),

        # -------------------------------------------------
        # DATES
        # -------------------------------------------------

        (
            "Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

def review_proposal_view(self, request, object_id):
    proposal = get_object_or_404(Proposal, pk=object_id)

    proposal_features = (
        proposal.proposal_features
        .all()
        .order_by("sort_order", "created_at")
    )

    screens = (
        proposal.screens
        .all()
        .order_by("sort_order", "created_at")
    )

    confirmed_total = sum(
        feature.total_price
        for feature in proposal_features
        if feature.status == "confirmed"
    )

    recommended_total = sum(
        feature.total_price
        for feature in proposal_features
        if feature.status == "recommended"
    )

    client_url = reverse(
        "proposals:client_proposal",
        kwargs={"token": proposal.public_token},
    )

    send_url = reverse(
        "admin:proposals_proposal_send",
        args=[proposal.pk],
    )

    regenerate_url = reverse(
        "admin:proposals_proposal_regenerate",
        args=[proposal.pk],
    )

    return render(
        request,
        "admin/proposals/review.html",
        {
            "proposal": proposal,
            "proposal_features": proposal_features,
            "screens": screens,
            "confirmed_total": confirmed_total,
            "recommended_total": recommended_total,
            "client_url": client_url,
            "send_url": send_url,
            "regenerate_url": regenerate_url,
        },
    )
# =========================================================
# PROPOSAL ADMIN
# =========================================================

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.db import transaction
from .models import Proposal

from proposals.services import (
    generate_initial_proposal,
    revise_proposal,
)




# =========================================================
# PROPOSAL ADMIN
# =========================================================

# =========================================================
# PROPOSAL ADMIN
# =========================================================

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from .forms import ProposalFeatureAdminForm

from .models import (
    Proposal,
    ProposalFeature,
    ProposalRequirement,
    ProposalScreen,
    ProposalRevision,
)

from .proposal_persistence import (
    recalculate_proposal,
)


# ============================================================
# PROPOSAL FEATURE INLINE
# ============================================================


# ============================================================
# PROPOSAL FEATURE INLINE
# ============================================================


# ============================================================
# REQUIREMENT INLINE
# ============================================================

from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from .forms import ProposalUpdateAdminForm

from .models import (
    Proposal,
    ProposalComment,
    ProposalUpdate,
    ProposalUpdateFile,
)

# Keep your existing imports for these:
# from .models import ProposalRequirement, ProposalFeature, ProposalScreen
# from .pricing import recalculate_proposal
# from .utils import pretty_json, get_client_proposal_url


# ============================================================
# PROPOSAL
# ============================================================
# ============================================================
# PROPOSAL ADMIN
# ============================================================

from decimal import Decimal

from django.contrib import admin, messages
from django.db.models import Prefetch
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    Proposal,
    ProposalMilestone,
    ProposalFeature,
    ProposalRequirement,
    ProposalScreen,
)

from .forms import ProposalFeatureAdminForm

from .proposal_persistence import (
    recalculate_proposal,
)




# ============================================================
# PROPOSAL MILESTONE INLINE
# ============================================================

class ProposalMilestoneInline(admin.TabularInline):
    model = ProposalMilestone

    extra = 1

    fields = (
        "order",
        "title",
        "amount",
        "percentage",
        "payment_required",
        "status",
        "payment_status",
        "admin_total_paid",
        "admin_outstanding",
        "admin_payment_progress",
        "due_date",
    )

    readonly_fields = (
        "payment_status",
        "admin_total_paid",
        "admin_outstanding",
        "admin_payment_progress",
    )

    ordering = (
        "order",
        "created_at",
    )

    show_change_link = True

    # ========================================================
    # QUERYSET
    # ========================================================

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        return queryset.select_related(
            "proposal",
        )

    # ========================================================
    # TOTAL PAID
    # ========================================================

    @admin.display(
        description="Paid",
    )
    def admin_total_paid(self, obj):

        if not obj or not obj.pk:
            return "-"

        currency = (
            obj.proposal.currency
            if obj.proposal
            else ""
        )

        return (
            f"{currency} "
            f"{obj.total_paid:,.2f}"
        )

    # ========================================================
    # OUTSTANDING
    # ========================================================

    @admin.display(
        description="Outstanding",
    )
    def admin_outstanding(self, obj):

        if not obj or not obj.pk:
            return "-"

        currency = (
            obj.proposal.currency
            if obj.proposal
            else ""
        )

        return (
            f"{currency} "
            f"{obj.outstanding_balance:,.2f}"
        )

    # ========================================================
    # PAYMENT PROGRESS
    # ========================================================

    @admin.display(
        description="Paid %",
    )
    def admin_payment_progress(self, obj):

        if not obj or not obj.pk:
            return "-"

        amount = obj.amount or Decimal("0.00")
        paid = obj.total_paid or Decimal("0.00")

        if amount <= Decimal("0.00"):
            return "0%"

        percentage = (
            paid / amount
        ) * Decimal("100")

        percentage = min(
            percentage,
            Decimal("100"),
        )

        return f"{percentage:.2f}%"


# ============================================================
# PROPOSAL FEATURE INLINE
# ============================================================

class ProposalFeatureInline(admin.TabularInline):

    model = ProposalFeature

    form = ProposalFeatureAdminForm

    extra = 1

    fields = (
        "feature_key",
        "name",
        "category",
        "complexity",
        "quantity",
        "scope_status",
        "status",
        "source",
        "unit_price",
        "total_price",
        "sort_order",
    )

    readonly_fields = (
        "name",
        "category",
        "unit_price",
        "total_price",
    )

    ordering = (
        "sort_order",
        "created_at",
    )


# ============================================================
# PROPOSAL REQUIREMENT INLINE
# ============================================================

class ProposalRequirementInline(admin.TabularInline):

    model = ProposalRequirement

    extra = 1

    fields = (
        "title",
        "description",
        "requirement_type",
        "status",
        "source",
        "sort_order",
    )

    ordering = (
        "sort_order",
        "created_at",
    )


# ============================================================
# PROPOSAL SCREEN INLINE
# ============================================================

class ProposalScreenInline(admin.TabularInline):

    model = ProposalScreen

    extra = 1

    fields = (
        "name",
        "screen_type",
        "complexity",
        "status",
        "sort_order",
    )

    ordering = (
        "sort_order",
        "created_at",
    )

    show_change_link = True


# ============================================================
# PROPOSAL ADMIN
# ============================================================

@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):

    # ========================================================
    # LIST DISPLAY
    # ========================================================

    list_display = (
        "title",
        "lead",
        "status",
        "version",
        "source",
        "currency",

        # Proposal pricing
        "total_price",

        # Procurement quotation pricing
        "admin_quotation_total",

        # Payments
        "admin_total_paid",
        "admin_outstanding",
        "admin_payment_status",
        "admin_payment_percentage",

        "accepted_at",
        "created_at",
    )

    # ========================================================
    # FILTERS
    # ========================================================

    list_filter = (
        "status",
        "source",
        "currency",
        "client_editable",
        "country",
        "created_at",
        "accepted_at",
    )

    # ========================================================
    # SEARCH
    # ========================================================

    search_fields = (
        "title",
        "lead__name",
        "lead__email",
        "lead__company",
        "public_token",

        # Procurement quotation
        "quote_request__title",
        "quote_request__tracking_reference",
    )

    # ========================================================
    # DATE NAVIGATION
    # ========================================================

    date_hierarchy = "created_at"

    # ========================================================
    # INLINE MODELS
    # ========================================================

    inlines = (
        ProposalMilestoneInline,
        ProposalFeatureInline,
        ProposalRequirementInline,
        ProposalScreenInline,
    )

    # ========================================================
    # ORDERING
    # ========================================================

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    save_on_top = True

    # ========================================================
    # READ ONLY
    # ========================================================

    readonly_fields = (
        # Core
        "id",
        "public_token",
        "version",

        # Proposal pricing
        "total_price",

        # Quotation
        "admin_quotation_tracking",
        "admin_quotation_status",
        "admin_quotation_subtotal",
        "admin_quotation_discount",
        "admin_quotation_tax",
        "admin_quotation_delivery",
        "admin_quotation_total",

        # Payment summary
        "admin_payment_total",
        "admin_payment_paid",
        "admin_payment_outstanding",
        "admin_payment_status",
        "admin_payment_percentage",

        # Milestones
        "admin_milestone_count",
        "admin_paid_milestone_count",
        "admin_next_payable_milestone",

        # Dates
        "created_at",
        "updated_at",
        "sent_at",
        "viewed_at",
        "accepted_at",
        "rejected_at",
    )

    # ========================================================
    # FIELDSETS
    # ========================================================

    fieldsets = (

        # ====================================================
        # PROPOSAL
        # ====================================================

        (
            "Proposal",
            {
                "fields": (
                    "id",
                    "title",
                    "status",
                    "source",
                    "version",
                    "lead",
                    "project_request",
                ),
            },
        ),

        # ====================================================
        # PROCUREMENT QUOTATION
        # ====================================================

        (
            "Procurement Quotation",
            {
                "fields": (
                    "quote_request",
                    "admin_quotation_tracking",
                    "admin_quotation_status",
                    "admin_quotation_subtotal",
                    "admin_quotation_discount",
                    "admin_quotation_tax",
                    "admin_quotation_delivery",
                    "admin_quotation_total",
                ),
            },
        ),

        # ====================================================
        # CLIENT PROPOSAL
        # ====================================================

        (
            "Client Proposal",
            {
                "fields": (
                    "client_summary",
                    "scope",
                    "pages",
                    "features",
                    "authentication",
                    "integrations",
                    "mobile",
                    "backend",
                    "devops",
                    "technical_scope",
                    "deliverables",
                    "assumptions",
                    "exclusions",
                    "timeline",
                    "milestones",
                ),
            },
        ),

        # ====================================================
        # REQUIREMENTS
        # ====================================================

        (
            "Requirements",
            {
                "fields": (
                    "business_objectives",
                    "confirmed_requirements",
                    "recommended_requirements",
                    "optional_future_features",
                    "security",
                    "recurring_costs",
                ),
            },
        ),

        # ====================================================
        # COMMERCIAL / PRICING
        # ====================================================

        (
            "Commercial / Pricing",
            {
                "fields": (
                    "country",
                    "currency",
                    "total_price",
                    "pricing_snapshot",
                ),
            },
        ),

        # ====================================================
        # PAYMENT SUMMARY
        # ====================================================

        (
            "Payment Summary",
            {
                "fields": (
                    "admin_payment_total",
                    "admin_payment_paid",
                    "admin_payment_outstanding",
                    "admin_payment_status",
                    "admin_payment_percentage",
                    "admin_milestone_count",
                    "admin_paid_milestone_count",
                    "admin_next_payable_milestone",
                ),
            },
        ),

        # ====================================================
        # AI
        # ====================================================

        (
            "Internal AI Analysis",
            {
                "fields": (
                    "ai_analysis",
                ),
            },
        ),

        # ====================================================
        # CLIENT ACCESS
        # ====================================================

        (
            "Client Access",
            {
                "fields": (
                    "public_token",
                    "client_editable",
                    "expires_at",
                ),
            },
        ),

        # ====================================================
        # DATES
        # ====================================================

        (
            "Dates",
            {
                "fields": (
                    "sent_at",
                    "viewed_at",
                    "accepted_at",
                    "rejected_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),

        # ====================================================
        # AUDIT
        # ====================================================

        (
            "Audit",
            {
                "fields": (
                    "created_by",
                ),
            },
        ),
    )

    # ========================================================
    # PROPOSAL / PAYMENT — LIST DISPLAY
    # ========================================================

    @admin.display(
        description="Total Paid",
        ordering="total_price",
    )
    def admin_total_paid(self, obj):
        return (
            f"{obj.currency} "
            f"{obj.total_paid:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Outstanding",
        ordering="total_price",
    )
    def admin_outstanding(self, obj):
        return (
            f"{obj.currency} "
            f"{obj.outstanding_balance:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Payment Status",
    )
    def admin_payment_status(self, obj):

        labels = {
            "paid": "Paid",
            "partially_paid": "Partially Paid",
            "unpaid": "Unpaid",
            "not_payable": "Not Payable",
        }

        status = obj.payment_status

        return labels.get(
            status,
            status.replace(
                "_",
                " ",
            ).title(),
        )

    # ========================================================

    @admin.display(
        description="Paid %",
    )
    def admin_payment_percentage(self, obj):

        total = (
            obj.total_price
            or Decimal("0.00")
        )

        if total <= Decimal("0.00"):
            return "0%"

        paid = (
            obj.total_paid
            or Decimal("0.00")
        )

        percentage = (
            paid / total
        ) * Decimal("100")

        percentage = min(
            percentage,
            Decimal("100"),
        )

        return f"{percentage:.2f}%"

    # ========================================================
    # QUOTATION — LIST DISPLAY
    # ========================================================

    @admin.display(
        description="Quotation Total",
        ordering="quote_request__total",
    )
    def admin_quotation_total(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "—"

        total = (
            quote.total
            or Decimal("0.00")
        )

        return (
            f"{quote.currency} "
            f"{total:,.2f}"
        )

    # ========================================================
    # QUOTATION — DETAIL
    # ========================================================

    @admin.display(
        description="Tracking Reference",
    )
    def admin_quotation_tracking(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "No quotation attached"

        return quote.tracking_reference or "—"

    # ========================================================

    @admin.display(
        description="Quotation Status",
    )
    def admin_quotation_status(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "—"

        return (
            quote.get_status_display()
            if hasattr(
                quote,
                "get_status_display",
            )
            else quote.status
        )

    # ========================================================

    @admin.display(
        description="Quotation Subtotal",
    )
    def admin_quotation_subtotal(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "—"

        return (
            f"{quote.currency} "
            f"{quote.subtotal:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Quotation Discount",
    )
    def admin_quotation_discount(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "—"

        return (
            f"{quote.currency} "
            f"{quote.discount:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Quotation Tax",
    )
    def admin_quotation_tax(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "—"

        return (
            f"{quote.currency} "
            f"{quote.tax:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Quotation Delivery",
    )
    def admin_quotation_delivery(self, obj):

        quote = getattr(
            obj,
            "quote_request",
            None,
        )

        if not quote:
            return "—"

        return (
            f"{quote.currency} "
            f"{quote.delivery_fee:,.2f}"
        )

    # ========================================================
    # PAYMENT — DETAIL SUMMARY
    # ========================================================

    @admin.display(
    description="Payment Total",
    )
    def admin_payment_total(self, obj):

        total = (
        obj.payment_total
        or Decimal("0.00")
    )

        return (
        f"{obj.currency} "
        f"{total:,.2f}"
    )

    # ========================================================

    @admin.display(
        description="Total Paid",
    )
    def admin_payment_paid(self, obj):

        paid = (
            obj.total_paid
            or Decimal("0.00")
        )

        return (
            f"{obj.currency} "
            f"{paid:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Outstanding Balance",
    )
    def admin_payment_outstanding(self, obj):

        outstanding = (
            obj.outstanding_balance
            or Decimal("0.00")
        )

        return (
            f"{obj.currency} "
            f"{outstanding:,.2f}"
        )

    # ========================================================

    @admin.display(
        description="Payment Status",
    )
    def admin_payment_status_detail(self, obj):
        return obj.payment_status

    # ========================================================

    @admin.display(
        description="Payment Percentage",
    )
    def admin_payment_percentage_detail(self, obj):

        total = (
            obj.total_price
            or Decimal("0.00")
        )

        if total <= Decimal("0.00"):
            return "0%"

        paid = (
            obj.total_paid
            or Decimal("0.00")
        )

        percentage = (
            paid / total
        ) * Decimal("100")

        percentage = min(
            percentage,
            Decimal("100"),
        )

        return f"{percentage:.2f}%"

    # ========================================================
    # MILESTONE COUNT
    # ========================================================

    @admin.display(
        description="Total Milestones",
    )
    def admin_milestone_count(self, obj):
        return obj.milestone_records.count()

    # ========================================================

    @admin.display(
        description="Paid Milestones",
    )
    def admin_paid_milestone_count(self, obj):

        return (
            obj.milestone_records
            .filter(
                payment_required=True,
                payment_status="paid",
            )
            .exclude(
                status="cancelled",
            )
            .count()
        )

    # ========================================================
    # NEXT PAYABLE MILESTONE
    # ========================================================

    @admin.display(
        description="Next Payable Milestone",
    )
    def admin_next_payable_milestone(self, obj):

        milestone = (
            obj.next_payable_milestone
        )

        if not milestone:
            return "None"

        return format_html(
            "<strong>#{}</strong> — {} — {} {:,.2f}",
            milestone.order,
            milestone.title,
            obj.currency,
            milestone.outstanding_balance,
        )

    # ========================================================
    # QUERYSET
    # ========================================================

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        return (
            queryset
            .select_related(
                "lead",
                "project_request",
                "quote_request",
                "created_by",
            )
            .prefetch_related(
                Prefetch(
                    "milestone_records",
                    queryset=(
                        ProposalMilestone.objects
                        .select_related(
                            "proposal",
                        )
                        .order_by(
                            "order",
                            "created_at",
                        )
                    ),
                ),
            )
        )

    # ========================================================
    # SAVE RELATED
    # ========================================================

    def save_related(
        self,
        request,
        form,
        formsets,
        change,
    ):

        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        proposal = form.instance

        try:

            recalculate_proposal(
                proposal,
            )

        except Exception as exc:

            self.message_user(
                request,
                (
                    "Proposal was saved, but "
                    "pricing recalculation failed: "
                    f"{exc}"
                ),
                level=messages.ERROR,
            )

            return

        self.message_user(
            request,
            (
                "Proposal saved and pricing "
                "recalculated successfully."
            ),
            level=messages.SUCCESS,
        )

    # ========================================================
    # CUSTOM URLS
    # ========================================================
    def send_proposal_view(
    self,
    request,
    object_id,
):
        proposal = self.get_object(
        request,
        object_id,
    )

        if proposal is None:
            self.message_user(
            request,
            "Proposal not found.",
            level=messages.ERROR,
        )

            return redirect(
            "admin:proposals_proposal_changelist"
        )

        if request.method != "POST":
            return redirect(
            reverse(
                "admin:proposals_proposal_review",
                args=[proposal.pk],
            )
        )

        try:
            proposal.status = "sent"
            proposal.sent_at = timezone.now()

            proposal.save(
            update_fields=[
                "status",
                "sent_at",
                "updated_at",
            ]
        )

            self.message_user(
            request,
            (
                f"Proposal '{proposal.title}' "
                "was sent successfully."
            ),
            level=messages.SUCCESS,
        )

        except Exception as exc:
            self.message_user(
            request,
            (
                "Failed to send proposal: "
                f"{exc}"
            ),
            level=messages.ERROR,
        )

        return redirect(
        reverse(
            "admin:proposals_proposal_review",
            args=[proposal.pk],
        )
    )
    def regenerate_proposal_view(self, request, object_id):
        """
        Regenerate/recalculate the proposal from its current data.
        """
        proposal = get_object_or_404(Proposal, pk=object_id)

        if request.method != "POST":
            return redirect(
            reverse(
                "admin:proposals_proposal_review",
                args=[proposal.pk],
            )
        )

        try:
            # Recalculate the proposal using the existing pricing logic.
            recalculate_proposal(proposal)

            self.message_user(
            request,
            f"Proposal {proposal.pk} was regenerated successfully.",
            messages.SUCCESS,
        )

        except Exception as exc:
            self.message_user(
            request,
            f"Unable to regenerate proposal: {exc}",
            messages.ERROR,
        )

        return redirect(
        reverse(
            "admin:proposals_proposal_review",
            args=[proposal.pk],
        )
    )
    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [

            path(
                "<path:object_id>/review/",
                self.admin_site.admin_view(
                    self.review_proposal_view,
                ),
                name=(
                    "proposals_proposal_review"
                ),
            ),

            path(
                "<path:object_id>/recalculate/",
                self.admin_site.admin_view(
                    self.recalculate_view,
                ),
                name=(
                    "proposals_proposal_recalculate"
                ),
            ),
            path(
            "<uuid:object_id>/send/",
            self.admin_site.admin_view(self.send_proposal_view),
            name="proposals_proposal_send",
        ),
        path(
            "<uuid:object_id>/regenerate/",
            self.admin_site.admin_view(self.regenerate_proposal_view),
            name="proposals_proposal_regenerate",
        ),
        ]

        return custom_urls + urls

    # ========================================================
    # REVIEW PROPOSAL
    # ========================================================

    def review_proposal_view(
        self,
        request,
        object_id,
    ):

        proposal = self.get_object(
            request,
            object_id,
        )

        if proposal is None:

            self.message_user(
                request,
                "Proposal not found.",
                level=messages.ERROR,
            )

            return redirect(
                "admin:proposals_proposal_changelist"
            )

        # ----------------------------------------------------
        # FEATURES
        # ----------------------------------------------------

        proposal_features = list(
            proposal.proposal_features
            .all()
            .order_by(
                "sort_order",
                "created_at",
            )
        )

        # ----------------------------------------------------
        # SCREENS
        # ----------------------------------------------------

        screens = list(
            proposal.screens
            .all()
            .order_by(
                "sort_order",
                "created_at",
            )
        )

        # ----------------------------------------------------
        # MILESTONES
        # ----------------------------------------------------

        milestones = list(
            proposal.milestone_records
            .all()
            .order_by(
                "order",
                "created_at",
            )
        )

        # ----------------------------------------------------
        # QUOTATION
        # ----------------------------------------------------

        quote_request = getattr(
            proposal,
            "quote_request",
            None,
        )

        quotation_summary = None

        if quote_request:

            quotation_summary = {
                "id": str(
                    quote_request.id
                ),

                "tracking_reference": (
                    quote_request.tracking_reference
                ),

                "title": (
                    quote_request.title
                ),

                "status": (
                    quote_request.get_status_display()
                ),

                "currency": (
                    quote_request.currency
                ),

                "subtotal": (
                    quote_request.subtotal
                    or Decimal("0.00")
                ),

                "discount": (
                    quote_request.discount
                    or Decimal("0.00")
                ),

                "tax": (
                    quote_request.tax
                    or Decimal("0.00")
                ),

                "delivery_fee": (
                    quote_request.delivery_fee
                    or Decimal("0.00")
                ),

                "total": (
                    quote_request.total
                    or Decimal("0.00")
                ),

                "formatted_total": (
                    quote_request.formatted_total
                ),
            }

        # ----------------------------------------------------
        # FORMAT JSON
        # ----------------------------------------------------

        proposal_json = {

            "scope": pretty_json(
                proposal.scope,
            ),

            "authentication": pretty_json(
                proposal.authentication,
            ),

            "mobile": pretty_json(
                proposal.mobile,
            ),

            "backend": pretty_json(
                proposal.backend,
            ),

            "devops": pretty_json(
                proposal.devops,
            ),

            "technical_scope": pretty_json(
                proposal.technical_scope,
            ),

            "security": pretty_json(
                proposal.security,
            ),

            "timeline": pretty_json(
                proposal.timeline,
            ),

            "ai_analysis": pretty_json(
                proposal.ai_analysis,
            ),
        }

        # ----------------------------------------------------
        # FORMAT SCREEN DATA
        # ----------------------------------------------------

        for screen in screens:

            screen.user_roles_display = (
                pretty_json(
                    screen.user_roles,
                )
            )

            screen.key_functionality_display = (
                pretty_json(
                    screen.key_functionality,
                )
            )

            screen.major_components_display = (
                pretty_json(
                    screen.major_components,
                )
            )

            screen.data_involved_display = (
                pretty_json(
                    screen.data_involved,
                )
            )

            screen.actions_display = (
                pretty_json(
                    screen.actions,
                )
            )

            screen.dependencies_display = (
                pretty_json(
                    screen.dependencies,
                )
            )

        # ----------------------------------------------------
        # FEATURE TOTALS
        # ----------------------------------------------------

        confirmed_total = sum(
            (
                feature.total_price
                or Decimal("0.00")
            )
            for feature in proposal_features
            if feature.status == "confirmed"
        )

        recommended_total = sum(
            (
                feature.total_price
                or Decimal("0.00")
            )
            for feature in proposal_features
            if feature.status == "recommended"
        )

        optional_total = sum(
            (
                feature.total_price
                or Decimal("0.00")
            )
            for feature in proposal_features
            if feature.status in (
                "optional",
                "future",
            )
        )

        # ----------------------------------------------------
        # PAYMENT SUMMARY
        # ----------------------------------------------------

        total_price = (
            proposal.total_price
            or Decimal("0.00")
        )

        total_paid = (
            proposal.total_paid
            or Decimal("0.00")
        )

        outstanding = (
            proposal.outstanding_balance
            or Decimal("0.00")
        )

        if total_price > Decimal("0.00"):

            payment_percentage = (
                total_paid
                / total_price
            ) * Decimal("100")

            payment_percentage = min(
                payment_percentage,
                Decimal("100"),
            )

        else:

            payment_percentage = Decimal(
                "0.00"
            )

        payment_summary = {

            "total": total_price,

            "total_paid": total_paid,

            "outstanding": outstanding,

            "status": proposal.payment_status,

            "percentage": payment_percentage,

            "milestone_count": len(
                milestones
            ),

            "paid_milestone_count": sum(
                1
                for milestone in milestones
                if (
                    milestone.payment_required
                    and milestone.payment_status
                    == "paid"
                )
            ),

            "milestones": milestones,

            "next_payable": (
                proposal.next_payable_milestone
            ),
        }

        # ----------------------------------------------------
        # CLIENT URL
        # ----------------------------------------------------

        client_url = get_client_proposal_url(
            proposal,
            request,
        )

        # ----------------------------------------------------
        # PROCUREMENT QUOTATION URL
        # ----------------------------------------------------

        procurement_client_url = None

        if quote_request:

            client_app_url = getattr(
                settings,
                "CLIENT_APP_URL",
                get_frontend_url(),
            )

            procurement_client_url = (
                f"{client_app_url.rstrip('/')}"
                f"/client/procurement/"
                f"{quote_request.id}"
            )

        # ----------------------------------------------------
        # SEND / REGENERATE
        # ----------------------------------------------------

        send_url = reverse(
            "admin:proposals_proposal_send",
            args=[
                proposal.pk,
            ],
        )

        regenerate_url = reverse(
            "admin:proposals_proposal_regenerate",
            args=[
                proposal.pk,
            ],
        )

        # ----------------------------------------------------
        # RENDER
        # ----------------------------------------------------

        return render(
            request,
            "admin/proposals/review.html",
            {
                "proposal": proposal,

                "proposal_features": (
                    proposal_features
                ),

                "screens": screens,

                "milestones": milestones,

                "confirmed_total": (
                    confirmed_total
                ),

                "recommended_total": (
                    recommended_total
                ),

                "optional_total": (
                    optional_total
                ),

                "proposal_json": (
                    proposal_json
                ),

                "payment_summary": (
                    payment_summary
                ),

                "quotation_summary": (
                    quotation_summary
                ),

                "client_url": (
                    client_url
                ),

                "procurement_client_url": (
                    procurement_client_url
                ),

                "send_url": (
                    send_url
                ),

                "regenerate_url": (
                    regenerate_url
                ),
            },
        )

    # ========================================================
    # RECALCULATE
    # ========================================================

    def recalculate_view(
        self,
        request,
        object_id,
    ):

        proposal = self.get_object(
            request,
            object_id,
        )

        if proposal is None:

            self.message_user(
                request,
                "Proposal not found.",
                level=messages.ERROR,
            )

            return redirect(
                "admin:proposals_proposal_changelist"
            )

        try:

            recalculate_proposal(
                proposal,
            )

            self.message_user(
                request,
                (
                    f"Proposal '{proposal.title}' "
                    "was recalculated successfully."
                ),
                level=messages.SUCCESS,
            )

        except Exception as exc:

            self.message_user(
                request,
                (
                    "Recalculation failed: "
                    f"{exc}"
                ),
                level=messages.ERROR,
            )

        return redirect(
            reverse(
                "admin:proposals_proposal_change",
                args=[
                    proposal.pk,
                ],
            )
        )

# ============================================================
# PROPOSAL COMMENTS — STANDALONE
# ============================================================

@admin.register(ProposalComment)
class ProposalCommentAdmin(admin.ModelAdmin):

    list_display = (
        "proposal",
        "comment_type",
        "milestone",
        "author",
        "author_type",
        "created_at",
    )

    list_filter = (
        "action",
        "author_type",
        "created_at",
    )

    search_fields = (
        "message",
        "proposal__title",
        "proposal__lead__name",
        "proposal__lead__email",
        "author__email",
        "author__first_name",
        "author__last_name",
    )

    autocomplete_fields = (
        "proposal",
        "author",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 50

    save_on_top = True

    fieldsets = (

        # ====================================================
        # PROJECT
        # ====================================================

        (
            "Project",
            {
                "fields": (
                    "proposal",
                    "milestone_id",
                )
            },
        ),

        # ====================================================
        # COMMENT
        # ====================================================

        (
            "Comment",
            {
                "fields": (
                    "message",
                    "action",
                    "author_type",
                    "author",
                )
            },
        ),

        # ====================================================
        # DATE
        # ====================================================

        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                )
            },
        ),
    )

    @admin.display(description="Type")
    def comment_type(self, obj):

        if obj.action == "accept":
            return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            "#16a34a",
            "Acceptance",
        )

        if obj.action == "decline":
            return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            "#dc2626",
            "Decline",
        )

        return format_html(
        '<span style="color:{}; font-weight:600;">{}</span>',
        "#2563eb",
        "Comment",
    )

    @admin.display(
        description="Milestone"
    )
    def milestone(self, obj):

        if obj.milestone_id:

            return (
                f"Milestone #{obj.milestone_id}"
            )

        return "General Project"


# ============================================================
# PROPOSAL UPDATES — STANDALONE
# ============================================================
from django.http import JsonResponse
from django.urls import path
from django.shortcuts import get_object_or_404
@admin.register(ProposalUpdate)
class ProposalUpdateAdmin(admin.ModelAdmin):

    form = ProposalUpdateAdminForm

    list_display = (
        "title",
        "client",
        "proposal",
        "milestone",
        "created_by",
        "file_count",
        "created_at",
    )

    list_filter = (
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "description",
        "proposal__title",
        "proposal__lead__name",
        "proposal__lead__email",
        "proposal__lead__company",
        "created_by__email",
    )

    autocomplete_fields = (
        "created_by",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 50

    save_on_top = True

    fieldsets = (
        (
            "Project",
            {
                "fields": (
                    "client",
                    "proposal",
                    "milestone",
                )
            },
        ),

        (
            "Update",
            {
                "fields": (
                    "title",
                    "description",
                )
            },
        ),

        (
            "Author",
            {
                "fields": (
                    "created_by",
                )
            },
        ),

        (
            "Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    # ========================================================
    # JAVASCRIPT
    # ========================================================

    class Media:
        js = (
            "admin/js/proposal_update_form.js",
        )

    # ========================================================
    # ADMIN URLS
    # ========================================================

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [
            path(
                "client-proposals/",
                self.admin_site.admin_view(
                    self.client_proposals_view
                ),
                name=(
                    "proposal_update_client_proposals"
                ),
            ),

            path(
                "proposal-milestones/",
                self.admin_site.admin_view(
                    self.proposal_milestones_view
                ),
                name=(
                    "proposal_update_proposal_milestones"
                ),
            ),
        ]

        return custom_urls + urls

    # ========================================================
    # CLIENT → PROPOSALS
    # ========================================================

    def client_proposals_view(
        self,
        request,
    ):

        client_id = request.GET.get(
            "client_id"
        )

        if not client_id:

            return JsonResponse(
                {
                    "proposals": []
                }
            )

        proposals = (
            Proposal.objects
            .filter(
                lead_id=client_id
            )
            .order_by(
                "-created_at"
            )
        )

        data = []

        for proposal in proposals:

            data.append(
                {
                    "id": str(
                        proposal.pk
                    ),
                    "title": proposal.title,
                    "status": proposal.status,
                    "version": proposal.version,
                }
            )

        return JsonResponse(
            {
                "proposals": data
            }
        )

    # ========================================================
    # PROPOSAL → MILESTONES
    # ========================================================

    def proposal_milestones_view(
        self,
        request,
    ):

        proposal_id = request.GET.get(
            "proposal_id"
        )

        if not proposal_id:

            return JsonResponse(
                {
                    "milestones": []
                }
            )

        proposal = get_object_or_404(
            Proposal,
            pk=proposal_id,
        )

        milestones = (
            proposal.milestones
            or []
        )

        data = []

        for index, milestone in enumerate(
            milestones,
            start=1,
        ):

            milestone = dict(
                milestone
            )

            milestone_id = (
                milestone.get("id")
                or index
            )

            title = (
                milestone.get("title")
                or milestone.get("name")
                or milestone.get("label")
                or f"Milestone {milestone_id}"
            )

            status = (
                milestone.get("status")
                or "pending"
            )

            data.append(
                {
                    "id": str(
                        milestone_id
                    ),
                    "title": title,
                    "status": status,
                }
            )

        return JsonResponse(
            {
                "milestones": data
            }
        )

    # ========================================================
    # CLIENT
    # ========================================================

    @admin.display(
        description="Client",
        ordering="proposal__lead__name",
    )
    def client(
        self,
        obj,
    ):

        if not obj.proposal:
            return "-"

        lead = obj.proposal.lead

        if not lead:
            return "-"

        name = getattr(
            lead,
            "name",
            None,
        )

        email = getattr(
            lead,
            "email",
            None,
        )

        if name and email:
            return f"{name} ({email})"

        return (
            name
            or email
            or str(lead)
        )

    # ========================================================
    # MILESTONE
    # ========================================================

    @admin.display(
        description="Milestone",
    )
    def milestone(
        self,
        obj,
    ):

        if not obj.milestone_id:
            return "General Project"

        if not obj.proposal:
            return (
                f"Milestone #{obj.milestone_id}"
            )

        milestones = (
            obj.proposal.milestones
            or []
        )

        for index, milestone in enumerate(
            milestones,
            start=1,
        ):

            milestone = dict(
                milestone
            )

            milestone_id = (
                milestone.get("id")
                or index
            )

            if str(
                milestone_id
            ) == str(
                obj.milestone_id
            ):

                title = (
                    milestone.get("title")
                    or milestone.get("name")
                    or milestone.get("label")
                )

                if title:
                    return title

                return (
                    f"Milestone #{milestone_id}"
                )

        return (
            f"Milestone #{obj.milestone_id}"
        )

    # ========================================================
    # FILE COUNT
    # ========================================================

    @admin.display(
        description="Files",
    )
    def file_count(
        self,
        obj,
    ):

        return obj.files.count()

# ============================================================
# PROPOSAL UPDATE FILES — STANDALONE
# ============================================================

@admin.register(ProposalUpdateFile)
class ProposalUpdateFileAdmin(admin.ModelAdmin):

    list_display = (
        "original_name",
        "update",
        "proposal",
        "file_type",
        "uploaded_at",
        "open_file",
    )

    list_filter = (
        "uploaded_at",
    )

    search_fields = (
        "original_name",
        "file",
        "update__title",
        "update__proposal__title",
        "update__proposal__lead__name",
        "update__proposal__lead__email",
    )

    autocomplete_fields = (
        "update",
    )

    readonly_fields = (
        "uploaded_at",
        "file_preview",
    )

    ordering = (
        "-uploaded_at",
    )

    list_per_page = 50

    save_on_top = True

    fieldsets = (

        # ====================================================
        # FILE
        # ====================================================

        (
            "File",
            {
                "fields": (
                    "update",
                    "file",
                    "original_name",
                    "file_preview",
                )
            },
        ),

        # ====================================================
        # METADATA
        # ====================================================

        (
            "Metadata",
            {
                "fields": (
                    "uploaded_at",
                )
            },
        ),
    )

    @admin.display(
        description="Project"
    )
    def proposal(self, obj):

        return obj.update.proposal

    @admin.display(
        description="Type"
    )
    def file_type(self, obj):

        if not obj.file:
            return "-"

        name = (
            obj.original_name
            or obj.file.name
        )

        extension = (
            name.rsplit(".", 1)[-1].upper()
            if "." in name
            else "FILE"
        )

        return extension

    @admin.display(
        description="File"
    )
    def open_file(self, obj):

        if not obj.file:
            return "-"

        return format_html(
            '<a href="{}" target="_blank">'
            'Open file'
            '</a>',
            obj.file.url,
        )

    @admin.display(
        description="Preview"
    )
    def file_preview(self, obj):

        if not obj.file:
            return "No file uploaded."

        name = (
            obj.original_name
            or obj.file.name
        )

        url = obj.file.url

        extension = (
            name.rsplit(".", 1)[-1].lower()
            if "." in name
            else ""
        )

        image_extensions = {
            "jpg",
            "jpeg",
            "png",
            "gif",
            "webp",
        }

        if extension in image_extensions:

            return format_html(
                """
                <div style="
                    margin-top:10px;
                    padding:10px;
                    background:#f8fafc;
                    border-radius:8px;
                ">
                    <img
                        src="{}"
                        style="
                            max-width:500px;
                            max-height:300px;
                            border-radius:6px;
                            display:block;
                        "
                    />

                    <br>

                    <a
                        href="{}"
                        target="_blank"
                    >
                        Open full image
                    </a>
                </div>
                """,
                url,
                url,
            )

        return format_html(
            '<a href="{}" target="_blank">'
            'Open {}'
            '</a>',
            url,
            name,
        )



# =========================================================
# PROPOSAL REVISION ADMIN
# =========================================================

@admin.register(ProposalRevision)
class ProposalRevisionAdmin(admin.ModelAdmin):

    list_display = (
        "proposal",
        "version",
        "source",
        "currency",
        "total_price",
        "created_at",
    )

    list_filter = (
        "source",
        "currency",
    )

    search_fields = (
        "proposal__title",
        "proposal__lead__name",
        "proposal__lead__email",
        "proposal__lead__company",
        "change_summary",
    )

    date_hierarchy = "created_at"

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    readonly_fields = (
        "id",
        "proposal",
        "version",
        "source",
        "title",
        "client_summary",
        "scope",
        "pages",
        "features",
        "authentication",
        "integrations",
        "mobile",
        "backend",
        "devops",
        "technical_scope",
        "deliverables",
        "assumptions",
        "exclusions",
        "timeline",
        "milestones",
        "country",
        "currency",
        "total_price",
        "pricing_snapshot",
        "ai_analysis",
        "change_summary",
        "created_at",
    )

    fieldsets = (

        # =================================================
        # REVISION
        # =================================================

        (
            "Revision",
            {
                "fields": (
                    "id",
                    "proposal",
                    "version",
                    "source",
                    "change_summary",
                    "created_at",
                )
            },
        ),

        # =================================================
        # PROPOSAL CONTENT
        # =================================================

        (
            "Proposal Content",
            {
                "fields": (
                    "title",
                    "client_summary",
                    "scope",
                    "pages",
                    "features",
                    "authentication",
                    "integrations",
                    "mobile",
                    "backend",
                    "devops",
                    "technical_scope",
                    "deliverables",
                    "assumptions",
                    "exclusions",
                    "timeline",
                    "milestones",
                )
            },
        ),

        # =================================================
        # PRICING
        # =================================================

        (
            "Commercial / Pricing",
            {
                "fields": (
                    "country",
                    "currency",
                    "total_price",
                    "pricing_snapshot",
                )
            },
        ),

        # =================================================
        # AI
        # =================================================

        (
            "Internal AI Analysis",
            {
                "fields": (
                    "ai_analysis",
                )
            },
        ),
    )



from django.contrib import admin
from .models import Proposal, ProposalFeature, ProposalRequirement, ProposalScreen


# --- Inline Models for Proposal Admin ---



class ProposalRequirementInline(admin.StackedInline):
    model = ProposalRequirement
    extra = 1
    fields = (
        ("title", "requirement_type"),
        ("status", "source", "sort_order"),
        "description",
    )
    ordering = ("sort_order",)




# --- Standalone Admin Registrations ---
from .forms import ProposalFeatureAdminForm,ProposalFeatureStandaloneAdminForm

# proposals/admin.py

from django.contrib import admin


from .models import ProposalFeature


@admin.register(ProposalFeature)
class ProposalFeatureAdmin(admin.ModelAdmin):

    form = ProposalFeatureStandaloneAdminForm

    list_display = (
        "name",
        "category",
        "description",
  
        "feature_key",
        "complexity",
        "quantity",
        "unit_price",
        "total_price",
        "scope_status",
        "status",
        "source",
        "proposal",
    )

    list_filter = (
        "category",
        "complexity",
        "description",
        "scope_status",
        "status",
        "source",
    )

    search_fields = (
        "name",
        "feature_key",
        "description",
        "category",
        "proposal__title",
    )

    readonly_fields = (
        "name",
        "category",
        "unit_price",
        "total_price",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Proposal",
            {
                "fields": (
                    "proposal",
                )
            },
        ),
        (
            "Feature",
            {
                "fields": (
                    "feature_key",
                    "complexity",
                    "description",
                    "quantity",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "name",
                    "category",
                    "unit_price",
                    "total_price",
                )
            },
        ),
        (
            "Scope",
            {
                "fields": (
                    "scope_status",
                    "status",
                    "source",
                )
            },
        ),
        (
            "Ordering",
            {
                "fields": (
                    "sort_order",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

from django.conf import settings



def review_proposal_view(self, request, object_id):
    proposal = get_object_or_404(Proposal, pk=object_id)

    proposal_features = (
        proposal.proposal_features
        .all()
        .order_by("sort_order", "created_at")
    )

    screens = (
        proposal.screens
        .all()
        .order_by("sort_order", "created_at")
    )

    confirmed_total = sum(
        feature.total_price
        for feature in proposal_features
        if feature.status == "confirmed"
    )

    recommended_total = sum(
        feature.total_price
        for feature in proposal_features
        if feature.status == "recommended"
    )

    client_url = reverse(
        "proposals:client_proposal",
        kwargs={"token": proposal.public_token},
    )

    # Procurement quotation
    quote_request = getattr(proposal, "quote_request", None)

    procurement_client_url = None

    if quote_request:
        procurement_client_url = (
            f"{settings.CLIENT_APP_URL.rstrip('/')}"
            f"/client/procurement/{quote_request.id}"
        )

    send_url = reverse(
        "admin:proposals_proposal_send",
        args=[proposal.pk],
    )

    regenerate_url = reverse(
        "admin:proposals_proposal_regenerate",
        args=[proposal.pk],
    )

    return render(
        request,
        "admin/proposals/review.html",
        {
            "proposal": proposal,
            "proposal_features": proposal_features,
            "screens": screens,
            "confirmed_total": confirmed_total,
            "recommended_total": recommended_total,
            "client_url": client_url,
            "procurement_client_url": procurement_client_url,
            "send_url": send_url,
            "regenerate_url": regenerate_url,
        },
    )



from django.contrib import admin
from .models import Proposal, ProposalMilestone

class ProposalMilestoneInline(admin.TabularInline):
    model = ProposalMilestone
    extra = 1
    fields = (
        "order", "title", "description",
        "amount", "percentage",
        "payment_required", "status", "payment_status",
        "due_date",
    )









@admin.register(ProposalRequirement)
class ProposalRequirementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "proposal",
        "requirement_type",
        "status",
        "source",
        "sort_order",
        "created_at",
    )
    list_filter = ("requirement_type", "status", "source", "created_at")
    search_fields = ("title", "description", "proposal__id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("proposal", "sort_order", "id")
    list_editable = ("status", "sort_order")
    




from .forms import ProposalScreenAdminForm


# ============================================================
# INLINE
# ============================================================

# ============================================================
# STANDALONE ADMIN
# ============================================================
@admin.register(ProposalScreen)
class ProposalScreenAdmin(admin.ModelAdmin):
    form = ProposalScreenAdminForm

    list_display = (
        "name",
        "proposal",
        "screen_type",
        "complexity",
        "status",
        "sort_order",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "screen_type",
        "complexity",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "purpose",
        "screen_type",
        "complexity",
        "proposal__title",
    )

    autocomplete_fields = (
        "proposal",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "proposal",
        "sort_order",
        "created_at",
    )

    fieldsets = (
        (
            "Proposal",
            {
                "fields": (
                    "proposal",
                ),
            },
        ),

        (
            "Screen Information",
            {
                "fields": (
                    "name",
                    "screen_type",
                    "purpose",
                    "complexity",
                ),
            },
        ),

        (
            "Users & Roles",
            {
                "fields": (
                    "user_roles",
                ),
                "description": (
                    "User roles that interact with this screen."
                ),
            },
        ),

        (
            "Functionality",
            {
                "fields": (
                    "key_functionality",
                    "major_components",
                    "data_involved",
                    "actions",
                ),
                "description": (
                    "Describe the functionality, major components, "
                    "data involved, and available actions."
                ),
            },
        ),

        (
            "Dependencies",
            {
                "fields": (
                    "dependencies",
                ),
            },
        ),

        (
            "Status & Ordering",
            {
                "fields": (
                    "status",
                    "sort_order",
                ),
            },
        ),

        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )