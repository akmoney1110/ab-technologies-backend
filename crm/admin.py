from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from .models import (
    Lead,
    QuoteRequest,
    ProjectRequest,
    SupportTicket,
)

from proposals.services import generate_initial_proposal


# =========================================================
# LEAD
# =========================================================



# =========================================================
# QUOTE REQUEST
# =========================================================
from decimal import Decimal

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Lead,
    QuoteRequest,
    ProcurementQuotationItem,
    ProjectRequest,
    SupportTicket,
)


# =========================================================
# LEAD ADMIN
# =========================================================
from decimal import Decimal

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Lead,
    QuoteRequest,
    ProcurementQuotationItem,
)


# =========================================================
# LEAD ADMIN
# =========================================================

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "company",
        "intent",
        "status_badge",
        "source",
        "country",
        "preferred_currency",
        "created_at",
    )

    list_filter = (
        "status",
        "source",
        "intent",
        "country",
        "created_at",
    )

    search_fields = (
        "name",
        "email",
        "phone",
        "company",
        "country",
        "country_code",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)

    list_per_page = 25

    fieldsets = (
        (
            "Lead Information",
            {
                "fields": (
                    "id",
                    "name",
                    "email",
                    "phone",
                    "company",
                )
            },
        ),
        (
            "Lead Classification",
            {
                "fields": (
                    "source",
                    "intent",
                    "status",
                )
            },
        ),
        (
            "Location & Currency",
            {
                "fields": (
                    "country",
                    "country_code",
                    "preferred_currency",
                )
            },
        ),
        (
            "Conversation",
            {
                "fields": (
                    "conversation",
                    "notes",
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

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "new": "#2563eb",
            "contacted": "#7c3aed",
            "qualified": "#d97706",
            "converted": "#16a34a",
            "lost": "#dc2626",
        }

        color = colors.get(obj.status, "#6b7280")

        return format_html(
            '<span style="'
            "display:inline-block;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "background:{};"
            "color:white;"
            "font-size:12px;"
            "font-weight:600;"
            '">{}</span>',
            color,
            obj.get_status_display(),
        )


# =========================================================
# PROCUREMENT QUOTATION ITEM INLINE
# =========================================================

class ProcurementQuotationItemInline(admin.TabularInline):
    model = ProcurementQuotationItem

    extra = 0

    fields = (
        "category",
        "name",
        "brand",
        "model",
        "quantity",
        "unit_price",
        "total_price_display",
        "specifications",
        "description",
    )

    readonly_fields = (
        "total_price_display",
    )

    show_change_link = True

    @admin.display(description="Item Total")
    def total_price_display(self, obj):
        if not obj.pk or obj.total_price is None:
            return mark_safe(
        '<span style="color:#d97706;font-weight:600;">'
        'Not priced'
        '</span>'
    )

        currency = (
            obj.quotation.currency
            if obj.quotation_id
            else "NGN"
        )

        amount = f"{obj.total_price:,.2f}"

        return format_html(
            "<strong>{} {}</strong>",
            currency,
            amount,
        )


# =========================================================
# PROCUREMENT QUOTATION ITEM ADMIN
# =========================================================

@admin.register(ProcurementQuotationItem)
class ProcurementQuotationItemAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "category",
        "brand",
        "model",
        "quantity",
        "unit_price_display",
        "total_price_display",
        "quotation",
        "created_at",
    )

    list_filter = (
        "category",
        "brand",
        "created_at",
    )

    search_fields = (
        "name",
        "category",
        "brand",
        "model",
        "quotation__title",
        "quotation__lead__name",
        "quotation__lead__email",
        "quotation__lead__company",
    )

    readonly_fields = (
        "id",
        "total_price",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "quotation",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    fieldsets = (
        (
            "Item",
            {
                "fields": (
                    "id",
                    "quotation",
                    "category",
                    "name",
                    "quantity",
                )
            },
        ),
        (
            "Product",
            {
                "fields": (
                    "brand",
                    "model",
                    "description",
                    "specifications",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "unit_price",
                    "total_price",
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

    @admin.display(description="Unit Price")
    def unit_price_display(self, obj):
        if obj.unit_price is None:
            return mark_safe(
            '<span style="color:#94a3b8;">Not priced</span>'
        )

        currency = obj.quotation.currency or "NGN"
        amount = f"{obj.unit_price:,.2f}"

        return format_html(
        "{} {}",
        currency,
        amount,
        )

    unit_price_display.short_description = "Unit Price"

    @admin.display(description="Total")
    def total_price_display(self, obj):
        if obj.total_price is None:
            return mark_safe(
            '<span style="color:#94a3b8;">Not priced</span>'
        )

        currency = obj.quotation.currency or "NGN"
        amount = f"{obj.total_price:,.2f}"

        return format_html(
        "{} {}",
        currency,
        amount,
    )

    total_price_display.short_description = "Total Price"
    


# =========================================================
# QUOTE REQUEST ADMIN
# =========================================================

from decimal import Decimal

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.html import format_html, mark_safe


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):

    # =====================================================
    # ADMIN CONFIGURATION
    # =====================================================

    list_display = (
        "title",
        "lead",
        "item_count",
        "status_badge",
        "currency",
        "subtotal_display",
        "total_display",
        "created_at",
    )

    list_filter = (
        "status",
        "currency",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "purpose",
        "notes",
        "lead__name",
        "lead__email",
        "lead__company",
    )

    readonly_fields = (
        "id",
        "subtotal",
        "total",
        "created_at",
        "updated_at",
        "pricing_status",
        "items_summary",
    )

    autocomplete_fields = (
        "lead",
    )

    inlines = (
        ProcurementQuotationItemInline,
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    # Custom admin template so we can add the
    # Generate Proposal button to the existing
    # Django admin submit row.
    change_form_template = (
        "admin/crm/quoterequest/change_form.html"
    )

    fieldsets = (
        (
            "Quotation Request",
            {
                "fields": (
                    "id",
                    "lead",
                    "title",
                    "description",
                    "purpose",
                )
            },
        ),
        (
            "Requested Items",
            {
                "fields": (
                    "items_summary",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "currency",
                    "subtotal",
                    "discount",
                    "tax",
                    "delivery_fee",
                    "total",
                    "pricing_status",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "notes",
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

    # =====================================================
    # DISPLAY HELPERS
    # =====================================================

    @admin.display(description="Items")
    def item_count(self, obj):
        count = obj.items.count()

        if count == 0:
            return format_html(
                '<span style="color:#dc2626;font-weight:600;">{}</span>',
                "No items",
            )

        return count

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "draft": "#6b7280",
            "priced": "#2563eb",
            "sent": "#7c3aed",
            "negotiation": "#d97706",
            "accepted": "#16a34a",
            "rejected": "#dc2626",
            "expired": "#991b1b",
        }

        color = colors.get(
            obj.status,
            "#6b7280",
        )

        return format_html(
            '<span style="'
            "display:inline-block;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "background:{};"
            "color:white;"
            "font-size:12px;"
            "font-weight:600;"
            '">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Subtotal")
    def subtotal_display(self, obj):
        return self.money(
            obj.subtotal,
            obj.currency,
        )

    @admin.display(description="Total")
    def total_display(self, obj):
        return format_html(
            "<strong>{}</strong>",
            self.money(
                obj.total,
                obj.currency,
            ),
        )

    @staticmethod
    def money(value, currency):
        value = value or Decimal("0")
        currency = currency or "NGN"

        return f"{currency} {value:,.2f}"

    # =====================================================
    # PRICING STATUS
    # =====================================================

    @admin.display(description="Pricing Status")
    def pricing_status(self, obj):
        items = list(obj.items.all())

        if not items:
            return format_html(
                '<span style="color:#dc2626;font-weight:600;">{}</span>',
                "No items",
            )

        unpriced = [
            item
            for item in items
            if item.unit_price is None
        ]

        if unpriced:
            return format_html(
                '<span style="color:#d97706;font-weight:600;">'
                "{} item(s) still need pricing"
                "</span>",
                len(unpriced),
            )

        return format_html(
            '<span style="color:#16a34a;font-weight:600;">{}</span>',
            "All items priced",
        )

    # =====================================================
    # ITEMS SUMMARY
    # =====================================================

    @admin.display(description="Items Summary")
    def items_summary(self, obj):
        items = list(
            obj.items.all()
        )

        if not items:
            return format_html(
                '<span style="color:#999;">{}</span>',
                "No items yet.",
            )

        rows = []

        for item in items:

            brand_model = " ".join(
                value.strip()
                for value in (
                    item.brand,
                    item.model,
                )
                if value and str(value).strip()
            )

            if not brand_model:
                brand_model = "Brand/model not specified"

            if item.unit_price is None:
                unit_price = "Not priced"
                total_price = "—"
            else:
                unit_price = self.money(
                    item.unit_price,
                    obj.currency,
                )

                total_price = self.money(
                    item.total_price or Decimal("0"),
                    obj.currency,
                )

            row = format_html(
                """
                <tr>
                    <td style="
                        padding:8px;
                        border-bottom:1px solid #eee;
                    ">
                        {}
                    </td>

                    <td style="
                        padding:8px;
                        border-bottom:1px solid #eee;
                    ">
                        <strong>{}</strong>
                        <br>
                        <small style="color:#666;">
                            {}
                        </small>
                    </td>

                    <td style="
                        padding:8px;
                        text-align:center;
                        border-bottom:1px solid #eee;
                    ">
                        {}
                    </td>

                    <td style="
                        padding:8px;
                        border-bottom:1px solid #eee;
                    ">
                        {}
                    </td>

                    <td style="
                        padding:8px;
                        border-bottom:1px solid #eee;
                    ">
                        <strong>{}</strong>
                    </td>
                </tr>
                """,
                item.category or "—",
                item.name or "—",
                brand_model,
                item.quantity,
                unit_price,
                total_price,
            )

            rows.append(row)

        table = format_html(
            """
            <table style="
                width:100%;
                border-collapse:collapse;
                background:#fff;
                border:1px solid #eee;
                border-radius:8px;
                overflow:hidden;
            ">
                <thead>
                    <tr style="background:#f8fafc;">
                        <th style="
                            text-align:left;
                            padding:8px;
                            border-bottom:1px solid #ddd;
                        ">
                            Category
                        </th>

                        <th style="
                            text-align:left;
                            padding:8px;
                            border-bottom:1px solid #ddd;
                        ">
                            Item
                        </th>

                        <th style="
                            text-align:center;
                            padding:8px;
                            border-bottom:1px solid #ddd;
                        ">
                            Qty
                        </th>

                        <th style="
                            text-align:left;
                            padding:8px;
                            border-bottom:1px solid #ddd;
                        ">
                            Unit Price
                        </th>

                        <th style="
                            text-align:left;
                            padding:8px;
                            border-bottom:1px solid #ddd;
                        ">
                            Total
                        </th>
                    </tr>
                </thead>

                <tbody>
                    {}
                </tbody>
            </table>
            """,
            mark_safe("".join(rows)),
        )

        return table

    # =====================================================
    # GENERATE PROPOSAL
    # =====================================================

    def response_change(self, request, obj):
        """
        Handles the custom "Generate Proposal" button.

        The normal Django admin Save button continues to work
        exactly as before.
        """

        if "_generate_proposal" not in request.POST:
            return super().response_change(
                request,
                obj,
            )

        return self.generate_proposal(
            request,
            obj,
        )


    def generate_proposal(self, request, quotation):
        """
    Complete QuoteRequest -> Gemini -> Proposal workflow.

    The workflow is:

        QuoteRequest
            ↓
        Validate fully priced
            ↓
        Gemini generates proposal content
            ↓
        Django creates Proposal
            ↓
        ProposalRevision v1

    Django remains the source of truth for all financial data.
        """

        # -------------------------------------------------
        # PERMISSION CHECK
        # -------------------------------------------------

        if not self.has_change_permission(
        request,
        quotation,
        ):
            raise PermissionDenied

        # -------------------------------------------------
        # MUST BE PRICED
        # -------------------------------------------------
        quotation.calculate_totals(save=True)
        quotation.refresh_from_db()
        if quotation.status != "priced":

            self.message_user(
                request,
                (
                "The proposal cannot be generated yet. "
                "The quotation must be fully priced first."
                ),
                level=messages.ERROR,
            )

            return self.response_post_save_change(
            request,
            quotation,
            )

        # -------------------------------------------------
        # MUST HAVE ITEMS
        # -------------------------------------------------

        items = list(
        quotation.items.all()
        )

        if not items:

            self.message_user(
            request,
            (
                "The proposal cannot be generated because "
                "this quotation has no items."
            ),
            level=messages.ERROR,
        )

            return self.response_post_save_change(
            request,
            quotation,
        )

        # -------------------------------------------------
        # EVERY ITEM MUST HAVE A PRICE
        # -------------------------------------------------

        unpriced_items = [
        item
        for item in items
        if item.unit_price is None
        ]

        if unpriced_items:

            names = ", ".join(
            item.name or "Unnamed item"
            for item in unpriced_items
        )

            self.message_user(
                request,
            (
                "The proposal cannot be generated because "
                f"the following item(s) are not priced: {names}"
            ),
            level=messages.ERROR,
        )

            return self.response_post_save_change(
            request,
            quotation,
        )

        # -------------------------------------------------
        # RECALCULATE QUOTATION
        # -------------------------------------------------

        quotation.calculate_totals(
            save=True
        )

        quotation.refresh_from_db()
        # -------------------------------------------------
        # COMPLETE QUOTE -> PROPOSAL WORKFLOW
        # -------------------------------------------------

        try:

            from ai.quoteproposal import (
            generate_and_create_quote_proposal,
            )

            proposal = generate_and_create_quote_proposal(
                quote_id=quotation.id,
                created_by=request.user,
            )

        except ValidationError as exc:

            self.message_user(
            request,
            (
                "Proposal generation failed: "
                f"{exc}"
            ),
            level=messages.ERROR,
        )

            return self.response_post_save_change(
            request,
            quotation,
        )

        except ValueError as exc:

            self.message_user(
            request,
            (
                "Proposal generation failed: "
                f"{exc}"
            ),
            level=messages.ERROR,
        )

            return self.response_post_save_change(
            request,
            quotation,
        )

        except Exception as exc:

            self.message_user(
            request,
            (
                "Proposal generation failed. "
                f"{exc}"
            ),
            level=messages.ERROR,
        )

            return self.response_post_save_change(
            request,
            quotation,
        )

    # -------------------------------------------------
    # SUCCESS
    # -------------------------------------------------

        self.message_user(
        request,
        (
            "Proposal generated successfully. "
            f"Proposal: {proposal.title} "
            f"(v{proposal.version})"
        ),
        level=messages.SUCCESS,
    )

        return self.response_post_save_change(
        request,
        quotation,
    )



    # =====================================================
    # SAVE
    # =====================================================

    def save_formset(
    self,
    request,
    form,
    formset,
    change,
):
        instances = formset.save(commit=False)

        for instance in instances:
            instance.calculate_total(save=False)
            instance.save()

        for deleted_object in formset.deleted_objects:
            deleted_object.delete()

        formset.save_m2m()
    # =====================================================
    # INLINE FORMSET SAVE
    # =====================================================

    
    # =====================================================
    # SAVE RELATED
    # =====================================================

    def save_related(self, request, form, formsets, change):
        super().save_related(
        request,
        form,
        formsets,
        change,
    )

        quotation = form.instance
        quotation.calculate_totals(save=True)

    # =====================================================
    # ITEM TOTAL
    # =====================================================

    
    # =====================================================
    # QUOTATION TOTALS
    # =====================================================

    
  

#
# =========================================================
# PROJECT REQUEST ADMIN
# =========================================================



# =========================================================
# SUPPORT TICKET ADMIN
# =========================================================

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):

    list_display = (
        "subject",
        "lead",
        "priority_badge",
        "status_badge",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "priority",
        "status",
        "created_at",
    )

    search_fields = (
        "subject",
        "description",
        "lead__name",
        "lead__email",
        "lead__company",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "lead",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(description="Priority")
    def priority_badge(self, obj):
        colors = {
            "low": "#6b7280",
            "normal": "#2563eb",
            "high": "#d97706",
            "urgent": "#dc2626",
        }

        color = colors.get(
            obj.priority,
            "#6b7280",
        )

        return format_html(
            '<span style="'
            "display:inline-block;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "background:{};"
            "color:white;"
            "font-size:12px;"
            "font-weight:600;"
            '">{}</span>',
            color,
            obj.get_priority_display(),
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "open": "#2563eb",
            "in_progress": "#d97706",
            "waiting": "#7c3aed",
            "resolved": "#16a34a",
            "closed": "#6b7280",
        }

        color = colors.get(
            obj.status,
            "#6b7280",
        )

        return format_html(
            '<span style="'
            "display:inline-block;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "background:{};"
            "color:white;"
            "font-size:12px;"
            "font-weight:600;"
            '">{}</span>',
            color,
            obj.get_status_display(),
        )
# =========================================================
# PROJECT REQUEST
# =========================================================

@admin.register(ProjectRequest)
class ProjectRequestAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "lead",
        "project_type",
        "status",
        "budget",
        "currency",
        "deadline",
        "created_at",
    )

    list_filter = (
        "status",
        "project_type",
        "currency",
    )

    search_fields = (
        "title",
        "description",
        "project_type",
        "lead__name",
        "lead__email",
        "lead__company",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Project Request",
            {
                "fields": (
                    "id",
                    "title",
                    "description",
                    "project_type",
                    "lead",
                )
            },
        ),

        (
            "Commercial",
            {
                "fields": (
                    "budget",
                    "currency",
                    "deadline",
                )
            },
        ),

        (
            "Status & Notes",
            {
                "fields": (
                    "status",
                    "notes",
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

    # -----------------------------------------------------
    # CUSTOM ADMIN URLS
    # -----------------------------------------------------

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [
            path(
                "<path:object_id>/generate-proposal/",
                self.admin_site.admin_view(
                    self.generate_proposal_view
                ),
                name="crm_projectrequest_generate_proposal",
            ),
        ]

        return custom_urls + urls

    # -----------------------------------------------------
    # GENERATE PROPOSAL
    # -----------------------------------------------------

    def generate_proposal_view(
        self,
        request,
        object_id,
    ):

        # -------------------------------------------------
        # Find project request
        # -------------------------------------------------

        try:

            project_request = (
                ProjectRequest.objects
                .select_related("lead")
                .get(pk=object_id)
            )

        except ProjectRequest.DoesNotExist:

            self.message_user(
                request,
                "Project request not found.",
                level=messages.ERROR,
            )

            return HttpResponseRedirect(
                reverse(
                    "admin:crm_projectrequest_changelist"
                )
            )

        # -------------------------------------------------
        # Make sure a lead exists
        # -------------------------------------------------

        if not project_request.lead:

            self.message_user(
                request,
                "This project request does not have a lead.",
                level=messages.ERROR,
            )

            return HttpResponseRedirect(
                reverse(
                    "admin:crm_projectrequest_change",
                    args=[project_request.pk],
                )
            )

        # -------------------------------------------------
        # Check for existing proposal
        # -------------------------------------------------

        existing_proposal = (
            project_request.proposals
            .order_by("-version", "-created_at")
            .first()
        )

        if existing_proposal:

            self.message_user(
                request,
                (
                    "A proposal already exists for this "
                    f"project request: "
                    f"{existing_proposal.title} "
                    f"(v{existing_proposal.version})."
                ),
                level=messages.WARNING,
            )

            return HttpResponseRedirect(
                reverse(
                    "admin:proposals_proposal_change",
                    args=[existing_proposal.pk],
                )
            )

        # -------------------------------------------------
        # Generate proposal
        # -------------------------------------------------

        try:

            proposal, revision = generate_initial_proposal(
                lead=project_request.lead,
                project_request=project_request,
                created_by=request.user,
            )

        except Exception as exc:

            self.message_user(
                request,
                (
                    "Proposal generation failed. "
                    f"Error: {exc}"
                ),
                level=messages.ERROR,
            )

            return HttpResponseRedirect(
                reverse(
                    "admin:crm_projectrequest_change",
                    args=[project_request.pk],
                )
            )

        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        self.message_user(
            request,
            (
                f"Proposal '{proposal.title}' "
                f"v{proposal.version} generated successfully."
            ),
            level=messages.SUCCESS,
        )

        # -------------------------------------------------
        # Take admin directly to proposal review
        # -------------------------------------------------

        return HttpResponseRedirect(
            reverse(
                "admin:proposals_proposal_change",
                args=[proposal.pk],
            )
        )


# =========================================================
# SUPPORT TICKET
# =========================================================
