from decimal import Decimal

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Lead,
    QuoteRequest,
    ProcurementQuotationItem,
    ProjectRequest,
    SupportTicket,
)

from proposals.services import generate_initial_proposal


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
    """Edit and price procurement items directly on a QuoteRequest."""

    model = ProcurementQuotationItem
    extra = 0
    show_change_link = True

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
            if obj.quotation_id and obj.quotation.currency
            else "NGN"
        )

        return format_html(
            '<strong style="white-space:nowrap;">{} {:,.2f}</strong>',
            currency,
            obj.total_price,
        )


# =========================================================
# PROCUREMENT QUOTATION ITEM ADMIN
# =========================================================

@admin.register(ProcurementQuotationItem)
class ProcurementQuotationItemAdmin(admin.ModelAdmin):
    """Standalone item view for searching and auditing quotation lines."""

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
        "description",
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

    list_select_related = (
        "quotation",
        "quotation__lead",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True
    empty_value_display = "—"

    fieldsets = (
        (
            "Quotation",
            {
                "fields": (
                    "id",
                    "quotation",
                )
            },
        ),
        (
            "Item Details",
            {
                "fields": (
                    "category",
                    "name",
                    "brand",
                    "model",
                    "quantity",
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
            "Audit",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        obj.calculate_total(save=False)
        super().save_model(request, obj, form, change)

        if obj.quotation_id:
            obj.quotation.calculate_totals(save=True)

    def delete_model(self, request, obj):
        quotation = obj.quotation
        super().delete_model(request, obj)
        quotation.calculate_totals(save=True)

    def delete_queryset(self, request, queryset):
        quotation_ids = list(
            queryset.values_list("quotation_id", flat=True).distinct()
        )
        super().delete_queryset(request, queryset)

        for quotation in QuoteRequest.objects.filter(pk__in=quotation_ids):
            quotation.calculate_totals(save=True)

    @admin.display(description="Unit Price", ordering="unit_price")
    def unit_price_display(self, obj):
        if obj.unit_price is None:
            return mark_safe(
                '<span style="color:#d97706;font-weight:600;">'
                'Not priced'
                '</span>'
            )

        currency = obj.quotation.currency or "NGN"
        return f"{currency} {obj.unit_price:,.2f}"

    @admin.display(description="Total", ordering="total_price")
    def total_price_display(self, obj):
        if obj.total_price is None:
            return mark_safe(
                '<span style="color:#94a3b8;">—</span>'
            )

        currency = obj.quotation.currency or "NGN"
        return format_html(
            '<strong style="white-space:nowrap;">{} {:,.2f}</strong>',
            currency,
            obj.total_price,
        )


# =========================================================
# QUOTE REQUEST ADMIN
# =========================================================

@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    """
    Procurement quotation workspace.

    QuoteRequest remains the financial source of truth. Items are priced
    inline, line totals are calculated by ProcurementQuotationItem, and the
    quotation totals are recalculated by QuoteRequest.calculate_totals().
    """

    list_display = (
        "title",
        "client_display",
        "request_type",
        "item_count",
        "pricing_status",
        "status_badge",
        "budget_display",
        "total_display",
        "deadline",
        "created_at",
    )

    list_filter = (
        "status",
        "request_type",
        "currency",
        "deadline",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "purpose",
        "notes",
        "tracking_reference",
        "lead__name",
        "lead__email",
        "lead__phone",
        "lead__company",
        "items__name",
        "items__brand",
        "items__model",
    )

    readonly_fields = (
        "id",
        "tracking_reference",
        "pricing_status",
        "items_summary",
        "subtotal",
        "total",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "lead",
    )

    inlines = (
        ProcurementQuotationItemInline,
    )

    list_select_related = (
        "lead",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True
    empty_value_display = "—"

    # Existing custom template that adds the Generate Proposal submit button.
    change_form_template = "admin/crm/quoterequest/change_form.html"

    actions = (
        "recalculate_selected_quotations",
    )

    fieldsets = (
        (
            "Client & Request",
            {
                "fields": (
                    "id",
                    "lead",
                    "title",
                    "request_type",
                    "description",
                    "purpose",
                )
            },
        ),
        (
            "Commercial Requirements",
            {
                "fields": (
                    "budget",
                    "currency",
                    "deadline",
                )
            },
        ),
        (
            "Quotation Overview",
            {
                "fields": (
                    "pricing_status",
                    "items_summary",
                ),
                "description": (
                    "Price the requested products in the quotation items below. "
                    "The summary and totals are calculated by Django."
                ),
            },
        ),
        (
            "Financial Summary",
            {
                "fields": (
                    "subtotal",
                    "discount",
                    "tax",
                    "delivery_fee",
                    "total",
                )
            },
        ),
        (
            "Workflow & Tracking",
            {
                "fields": (
                    "status",
                    "tracking_reference",
                    "notes",
                )
            },
        ),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    # =====================================================
    # QUERYSET
    # =====================================================

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("lead")
            .prefetch_related("items")
            .annotate(_admin_item_count=Count("items", distinct=True))
        )

    # =====================================================
    # LIST / DISPLAY HELPERS
    # =====================================================

    @admin.display(description="Client", ordering="lead__name")
    def client_display(self, obj):
        if not obj.lead_id:
            return "—"

        name = obj.lead.name or obj.lead.email or "Client"
        secondary = obj.lead.company or obj.lead.email or ""

        if secondary and secondary != name:
            return format_html(
                '<strong>{}</strong><br><span style="color:#64748b;font-size:11px;">{}</span>',
                name,
                secondary,
            )

        return name

    @admin.display(description="Items", ordering="_admin_item_count")
    def item_count(self, obj):
        count = getattr(obj, "_admin_item_count", None)
        if count is None:
            count = obj.items.count()

        if count == 0:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">No items</span>'
            )

        return format_html(
            '<span style="font-weight:700;">{}</span>',
            count,
        )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "draft": ("#475569", "#f1f5f9"),
            "priced": ("#1d4ed8", "#dbeafe"),
            "sent": ("#6d28d9", "#ede9fe"),
            "negotiation": ("#b45309", "#fef3c7"),
            "accepted": ("#15803d", "#dcfce7"),
            "rejected": ("#b91c1c", "#fee2e2"),
            "expired": ("#7f1d1d", "#fee2e2"),
            "completed": ("#166534", "#dcfce7"),
        }

        foreground, background = colors.get(
            obj.status,
            ("#475569", "#f1f5f9"),
        )

        label = (
            obj.get_status_display()
            if hasattr(obj, "get_status_display")
            else obj.status
        )

        return format_html(
            '<span style="display:inline-block;padding:4px 10px;'
            'border-radius:999px;background:{};color:{};font-size:12px;'
            'font-weight:700;white-space:nowrap;">{}</span>',
            background,
            foreground,
            label,
        )

    @admin.display(description="Budget", ordering="budget")
    def budget_display(self, obj):
        if obj.budget is None:
            return format_html(
                '<span style="color:#94a3b8;">Not specified</span>'
            )
        return self.money(obj.budget, obj.currency)

    @admin.display(description="Total", ordering="total")
    def total_display(self, obj):
        return format_html(
            '<strong style="white-space:nowrap;">{}</strong>',
            self.money(obj.total, obj.currency),
        )

    @staticmethod
    def money(value, currency):
        value = value or Decimal("0.00")
        currency = currency or "NGN"
        return f"{currency} {value:,.2f}"

    # =====================================================
    # PRICING STATUS
    # =====================================================

    @admin.display(description="Pricing")
    def pricing_status(self, obj):
        items = list(obj.items.all())

        if not items:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">No items</span>'
            )

        unpriced = [item for item in items if item.unit_price is None]

        if unpriced:
            return format_html(
                '<span style="color:#b45309;font-weight:700;">{} unpriced</span>',
                len(unpriced),
            )

        return format_html(
            '<span style="color:#15803d;font-weight:700;">Ready</span>'
        )

    # =====================================================
    # ITEMS SUMMARY
    # =====================================================

    @admin.display(description="Quotation Items Summary")
    def items_summary(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span style="color:#64748b;">Save the quotation first, then add items below.</span>'
            )

        items = list(obj.items.all())

        if not items:
            return format_html(
                '<div style="padding:12px;border:1px solid #fecaca;'
                'background:#fef2f2;border-radius:8px;color:#991b1b;">'
                '<strong>No quotation items yet.</strong> Add the requested products '
                'using the inline section below.</div>'
            )

        rows = []

        for item in items:
            brand_model = " ".join(
                str(value).strip()
                for value in (item.brand, item.model)
                if value and str(value).strip()
            ) or "—"

            if item.unit_price is None:
                unit_price = mark_safe(
                    '<span style="color:#b45309;font-weight:600;">Not priced</span>'
                )
                total_price = "—"
            else:
                unit_price = self.money(item.unit_price, obj.currency)
                total_price = self.money(
                    item.total_price or Decimal("0.00"),
                    obj.currency,
                )

            rows.append(
                format_html(
                    '<tr>'
                    '<td style="padding:8px;border-bottom:1px solid #e5e7eb;">{}</td>'
                    '<td style="padding:8px;border-bottom:1px solid #e5e7eb;">'
                    '<strong>{}</strong><br><small style="color:#64748b;">{}</small></td>'
                    '<td style="padding:8px;text-align:center;border-bottom:1px solid #e5e7eb;">{}</td>'
                    '<td style="padding:8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;">{}</td>'
                    '<td style="padding:8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;">'
                    '<strong>{}</strong></td>'
                    '</tr>',
                    item.category or "—",
                    item.name or "—",
                    brand_model,
                    item.quantity,
                    unit_price,
                    total_price,
                )
            )

        return format_html(
            '<div style="overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;background:#fff;'
            'border:1px solid #e5e7eb;">'
            '<thead><tr style="background:#f8fafc;">'
            '<th style="text-align:left;padding:8px;">Category</th>'
            '<th style="text-align:left;padding:8px;">Item</th>'
            '<th style="text-align:center;padding:8px;">Qty</th>'
            '<th style="text-align:left;padding:8px;">Unit Price</th>'
            '<th style="text-align:left;padding:8px;">Total</th>'
            '</tr></thead><tbody>{}</tbody></table></div>',
            mark_safe("".join(str(row) for row in rows)),
        )

    # =====================================================
    # GENERATE PROPOSAL
    # =====================================================

    def response_change(self, request, obj):
        """Handle the existing custom Generate Proposal submit button."""
        if "_generate_proposal" not in request.POST:
            return super().response_change(request, obj)

        return self.generate_proposal(request, obj)

    def generate_proposal(self, request, quotation):
        """
        QuoteRequest -> validated pricing -> AI proposal -> persisted Proposal.

        Financial values remain controlled by Django/QuoteRequest.
        """
        if not self.has_change_permission(request, quotation):
            raise PermissionDenied

        # Always recalculate before validating readiness.
        quotation.calculate_totals(save=True)
        quotation.refresh_from_db()

        items = list(quotation.items.all())

        if not items:
            self.message_user(
                request,
                "The proposal cannot be generated because this quotation has no items.",
                level=messages.ERROR,
            )
            return self.response_post_save_change(request, quotation)

        unpriced_items = [item for item in items if item.unit_price is None]

        if unpriced_items:
            names = ", ".join(
                item.name or "Unnamed item"
                for item in unpriced_items
            )
            self.message_user(
                request,
                "The proposal cannot be generated because the following item(s) "
                f"are not priced: {names}",
                level=messages.ERROR,
            )
            return self.response_post_save_change(request, quotation)

        # calculate_totals() is expected to mark a fully priced quotation as priced.
        if quotation.status != "priced":
            self.message_user(
                request,
                "The quotation is fully priced, but its status is not 'Priced'. "
                "Recalculate/save the quotation and try again.",
                level=messages.ERROR,
            )
            return self.response_post_save_change(request, quotation)

        try:
            from ai.quoteproposal import generate_and_create_quote_proposal

            proposal = generate_and_create_quote_proposal(
                quote_id=quotation.id,
                created_by=request.user,
            )

        except (ValidationError, ValueError) as exc:
            self.message_user(
                request,
                f"Proposal generation failed: {exc}",
                level=messages.ERROR,
            )
            return self.response_post_save_change(request, quotation)

        except Exception as exc:
            self.message_user(
                request,
                f"Proposal generation failed. {exc}",
                level=messages.ERROR,
            )
            return self.response_post_save_change(request, quotation)

        self.message_user(
            request,
            "Proposal generated successfully. "
            f"Proposal: {proposal.title} (v{proposal.version})",
            level=messages.SUCCESS,
        )

        # Take the administrator directly to the generated proposal.
        try:
            return HttpResponseRedirect(
                reverse(
                    "admin:proposals_proposal_change",
                    args=[proposal.pk],
                )
            )
        except Exception:
            return self.response_post_save_change(request, quotation)

    # =====================================================
    # SAVE / RECALCULATION
    # =====================================================

    def save_formset(self, request, form, formset, change):
        """Calculate every edited line before it is saved."""
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, ProcurementQuotationItem):
                instance.calculate_total(save=False)
            instance.save()

        for deleted_object in formset.deleted_objects:
            deleted_object.delete()

        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        """Recalculate QuoteRequest totals after all inline items are saved."""
        super().save_related(request, form, formsets, change)
        quotation = form.instance
        quotation.calculate_totals(save=True)

    @admin.action(description="Recalculate selected quotation totals")
    def recalculate_selected_quotations(self, request, queryset):
        updated = 0
        failed = 0

        for quotation in queryset:
            try:
                quotation.calculate_totals(save=True)
                updated += 1
            except Exception:
                failed += 1

        if updated:
            self.message_user(
                request,
                f"Recalculated {updated} quotation(s).",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"Could not recalculate {failed} quotation(s).",
                level=messages.WARNING,
            )


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
