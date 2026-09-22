import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class PricingRule(models.Model):
    CATEGORY_CHOICES = [
        ("website", "Website"),
        ("mobile", "Mobile"),
        ("backend", "Backend/API"),
        ("authentication", "Authentication"),
        ("integration", "Integration"),
        ("devops", "DevOps"),
        ("feature", "Feature"),
        ("training", "Training"),
        ("procurement", "Procurement"),
        ("consulting", "Consulting"),
        ("other", "Other"),
    ]

    UNIT_CHOICES = [
        ("fixed", "Fixed"),
        ("per_unit", "Per Unit"),
        ("per_page", "Per Page"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    

    code = models.CharField(
        max_length=100,
        unique=True,
    )

    name = models.CharField(
        max_length=255,
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
    )

    region = models.CharField(
        max_length=100,
        default="NG",
    )

    currency = models.CharField(
        max_length=10,
        default="NGN",
    )

    unit = models.CharField(
        max_length=30,
        choices=UNIT_CHOICES,
        default="fixed",
    )
    

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    priority = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.currency} {self.price})"

class Proposal(models.Model):

    # ========================================================
    # STATUS
    # ========================================================

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready for Review"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("revision_requested", "Revision Requested"),
        ("accepted", "Accepted"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    SOURCE_CHOICES = [
        ("project_request", "Project Request"),
        ("quote_request", "Quote Request"),
        ("manual", "Manual"),
    ]

    # ========================================================
    # IDENTITY
    # ========================================================

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    public_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.CASCADE,
        related_name="proposals",
    )

    project_request = models.ForeignKey(
        "crm.ProjectRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposals",
    )

    quote_request = models.ForeignKey(
        "crm.QuoteRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposals",
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="proposals",
    )

    # ========================================================
    # EXECUTIVE / CLIENT INFORMATION
    # ========================================================

    executive_summary = models.TextField(
        blank=True,
    )

    business_objectives = models.JSONField(
        default=list,
        blank=True,
    )

    confirmed_requirements = models.JSONField(
        default=list,
        blank=True,
    )

    recommended_requirements = models.JSONField(
        default=list,
        blank=True,
    )

    optional_future_features = models.JSONField(
        default=list,
        blank=True,
    )

    security = models.JSONField(
        default=dict,
        blank=True,
    )

    recurring_costs = models.JSONField(
        default=list,
        blank=True,
    )

    # ========================================================
    # PROPOSAL META
    # ========================================================

    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="project_request",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
    )

    version = models.PositiveIntegerField(
        default=1,
    )

    title = models.CharField(
        max_length=255,
    )

    client_summary = models.TextField(
        blank=True,
    )

    # ========================================================
    # COMPLETE SCOPE
    # ========================================================

    scope = models.JSONField(
        default=dict,
        blank=True,
    )

    pages = models.JSONField(
        default=list,
        blank=True,
    )

    features = models.JSONField(
        default=list,
        blank=True,
    )

    authentication = models.JSONField(
        default=dict,
        blank=True,
    )

    integrations = models.JSONField(
        default=list,
        blank=True,
    )

    mobile = models.JSONField(
        default=dict,
        blank=True,
    )

    backend = models.JSONField(
        default=dict,
        blank=True,
    )

    devops = models.JSONField(
        default=dict,
        blank=True,
    )

    technical_scope = models.JSONField(
        default=dict,
        blank=True,
    )

    deliverables = models.JSONField(
        default=list,
        blank=True,
    )

    assumptions = models.JSONField(
        default=list,
        blank=True,
    )

    exclusions = models.JSONField(
        default=list,
        blank=True,
    )

    timeline = models.JSONField(
        default=dict,
        blank=True,
    )

    # ========================================================
    # LEGACY / CLIENT-FACING JSON MILESTONES
    # ========================================================

    milestones = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Internal and client-facing project milestones. "
            "Relational ProposalMilestone records are used "
            "for payment tracking."
        ),
    )

    # ========================================================
    # CLIENT / PRICING
    # ========================================================

    country = models.CharField(
        max_length=100,
        blank=True,
    )

    currency = models.CharField(
        max_length=10,
        default="NGN",
    )

    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # Internal pricing snapshot
    pricing_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    # Internal AI analysis
    ai_analysis = models.JSONField(
        default=dict,
        blank=True,
    )

    client_editable = models.BooleanField(
        default=True,
    )

    # ========================================================
    # ACCEPTED VERSION
    # ========================================================

    accepted_version = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # ========================================================
    # DATES
    # ========================================================

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    viewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ========================================================
    # AUDIT
    # ========================================================

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_proposals",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # ========================================================
    # META
    # ========================================================

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - v{self.version}"

    # ========================================================
    # BASIC PROPERTIES
    # ========================================================

    @property
    def formatted_price(self):
        """
        The Proposal's own stored price.

        For procurement payment calculations, use
        payment_total instead.
        """

        return (
            f"{self.currency} "
            f"{self.total_price:,.2f}"
        )

    @property
    def is_accepted(self):
        return self.status == "accepted"

    @property
    def latest_revision(self):
        return (
            self.revisions
            .order_by("-version")
            .first()
        )

    # ========================================================
    # FINANCIAL SOURCE
    # ========================================================

    @property
    def is_procurement(self):
        """
        Whether this proposal is backed by a procurement
        quotation.
        """

        return bool(self.quote_request_id)

    
    @property
    def payment_total(self):    
        if self.quote_request_id:
            quote = self.quote_request

            # Accepted client revision takes precedence
            accepted_revision = (
            quote.client_revisions
            .filter(status="accepted")
            .order_by("-revision_number")
            .first()
        )

            if accepted_revision:
                return accepted_revision.total or Decimal("0.00")

            return quote.total or Decimal("0.00")

        return self.total_price or Decimal("0.00")

    @property
    def formatted_payment_total(self):
        return (
            f"{self.currency} "
            f"{self.payment_total:,.2f}"
        )

    # ========================================================
    # COMPLETION
    # ========================================================

    def check_and_mark_completed(self):
        """
        Legacy JSON milestone completion check.

        Relational ProposalMilestone records are used by the
        payment system, while this method remains compatible
        with older proposal data.
        """

        milestones = self.milestones or []

        if not milestones:
            return False

        all_completed = all(
            str(
                milestone.get("status", "")
            ).lower()
            in {
                "completed",
                "complete",
                "done",
            }
            for milestone in milestones
        )

        if (
            all_completed
            and self.status != "completed"
        ):
            self.status = "completed"

            self.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return True

        return False

    # ========================================================
    # PAYMENT
    # ========================================================

    @property
    def total_paid(self):
        """
        Total amount actually retained from successful
        payments.

        Successful payments:
            successful
            partially_refunded

        Fully refunded payments are excluded because their
        status becomes 'refunded'.
        """

        payments = self.payments.filter(
            status__in=[
                "successful",
                "partially_refunded",
            ]
        )

        total = Decimal("0.00")

        for payment in payments:

            amount = (
                payment.amount
                or Decimal("0.00")
            )

            refunded = (
                payment.refunded_amount
                or Decimal("0.00")
            )

            retained = max(
                Decimal("0.00"),
                amount - refunded,
            )

            total += retained

        return max(
            Decimal("0.00"),
            total,
        )

    @property
    def outstanding_balance(self):
        """
        Amount still owed.

        Procurement:
            QuoteRequest.total - total_paid

        Project:
            Proposal.total_price - total_paid
        """

        return max(
            Decimal("0.00"),
            self.payment_total - self.total_paid,
        )

    @property
    def payment_status(self):
        """
        Current financial state of the proposal.
        """

        total = self.payment_total

        if total <= Decimal("0.00"):
            return "not_payable"

        paid = self.total_paid

        if paid <= Decimal("0.00"):
            return "unpaid"

        if paid >= total:
            return "paid"

        return "partially_paid"

    @property
    def payment_percentage(self):
        """
        Percentage of the authoritative payment total that
        has actually been paid and retained.
        """

        total = self.payment_total

        if total <= Decimal("0.00"):
            return Decimal("0.00")

        percentage = (
            self.total_paid / total
        ) * Decimal("100")

        return min(
            Decimal("100.00"),
            percentage,
        ).quantize(
            Decimal("0.01")
        )

    @property
    def formatted_total_paid(self):
        return (
            f"{self.currency} "
            f"{self.total_paid:,.2f}"
        )

    @property
    def formatted_outstanding_balance(self):
        return (
            f"{self.currency} "
            f"{self.outstanding_balance:,.2f}"
        )

    # ========================================================
    # PAYMENT / MILESTONE SUMMARY
    # ========================================================

    @property
    def milestone_count(self):
        return self.milestone_records.count()

    @property
    def payment_required_milestone_count(self):
        return (
            self.milestone_records
            .filter(
                payment_required=True,
            )
            .exclude(
                status="cancelled",
            )
            .count()
        )

    @property
    def paid_milestone_count(self):
        return (
            self.milestone_records
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

    @property
    def next_payable_milestone(self):
        """
        Return the first payment-required milestone that can
        currently receive payment.

        Payment milestones are sequential.

        Example:

            Milestone 1 → Paid
            Milestone 2 → Payable
            Milestone 3 → Locked
        """

        milestones = list(
            self.milestone_records
            .filter(
                payment_required=True,
            )
            .exclude(
                status="cancelled",
            )
            .order_by(
                "order",
                "created_at",
            )
        )

        for milestone in milestones:

            # Already fully paid
            if milestone.payment_status == "paid":
                continue

            # Nothing remains to pay
            if (
                milestone.outstanding_balance
                <= Decimal("0.00")
            ):
                continue

            # Explicitly locked
            if milestone.status == "locked":
                continue

            # ------------------------------------------------
            # Check previous payment-required milestones
            # ------------------------------------------------

            previous_milestones = [
                item
                for item in milestones
                if item.order < milestone.order
            ]

            if any(
                item.payment_status != "paid"
                for item in previous_milestones
            ):
                continue

            return milestone

        return None

    # ========================================================
    # NEXT PAYMENT INFORMATION
    # ========================================================

    @property
    def next_payment_amount(self):
        """
        Amount currently available for payment on the next
        payable milestone.
        """

        milestone = self.next_payable_milestone

        if not milestone:
            return Decimal("0.00")

        return max(
            Decimal("0.00"),
            milestone.outstanding_balance,
        )

    @property
    def has_payable_milestone(self):
        return (
            self.next_payable_milestone
            is not None
        )

    # ========================================================
    # LAST PAYMENT
    # ========================================================

    @property
    def last_payment_at(self):
        """
        Most recent successful payment date.
        """

        payment = (
            self.payments
            .filter(
                status__in=[
                    "successful",
                    "partially_refunded",
                ],
                paid_at__isnull=False,
            )
            .order_by("-paid_at")
            .first()
        )

        return (
            payment.paid_at
            if payment
            else None
        )

    @property
    def last_payment(self):
        """
        Most recent successful payment object.
        """

        return (
            self.payments
            .filter(
                status__in=[
                    "successful",
                    "partially_refunded",
                ],
                paid_at__isnull=False,
            )
            .order_by("-paid_at")
            .first()
        )

    # ========================================================
    # PAYMENT COMPLETION
    # ========================================================

    @property
    def is_fully_paid(self):
        """
        Whether the authoritative proposal/payment total has
        been completely paid.
        """

        total = self.payment_total

        if total <= Decimal("0.00"):
            return False

        return (
            self.outstanding_balance
            <= Decimal("0.00")
        )

    @property
    def is_partially_paid(self):
        return (
            self.total_paid > Decimal("0.00")
            and not self.is_fully_paid
        )

    # ========================================================
    # PAYMENT LABEL
    # ========================================================

    @property
    def payment_status_label(self):
        labels = {
            "paid": "Paid",
            "partially_paid": "Partially Paid",
            "unpaid": "Unpaid",
            "not_payable": "Not Payable",
        }

        status = self.payment_status

        return labels.get(
            status,
            status.replace(
                "_",
                " ",
            ).title(),
        )





class ProposalRevision(models.Model):

    SOURCE_CHOICES = [
        ("ai", "AI"),
        ("client", "Client"),
        ("staff", "Staff"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="revisions",
    )

    version = models.PositiveIntegerField()

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="ai",
    )

    title = models.CharField(
        max_length=255,
    )

    client_summary = models.TextField(
        blank=True,
    )

    scope = models.JSONField(
        default=dict,
        blank=True,
    )

    pages = models.JSONField(
        default=list,
        blank=True,
    )

    features = models.JSONField(
        default=list,
        blank=True,
    )

    authentication = models.JSONField(
        default=dict,
        blank=True,
    )

    integrations = models.JSONField(
        default=list,
        blank=True,
    )

    mobile = models.JSONField(
        default=dict,
        blank=True,
    )

    backend = models.JSONField(
        default=dict,
        blank=True,
    )

    devops = models.JSONField(
        default=dict,
        blank=True,
    )

    technical_scope = models.JSONField(
        default=dict,
        blank=True,
    )

    deliverables = models.JSONField(
        default=list,
        blank=True,
    )

    assumptions = models.JSONField(
        default=list,
        blank=True,
    )

    exclusions = models.JSONField(
        default=list,
        blank=True,
    )

    timeline = models.JSONField(
        default=dict,
        blank=True,
    )

    milestones = models.JSONField(
        default=list,
        blank=True,
    )

    country = models.CharField(
        max_length=100,
        blank=True,
    )

    currency = models.CharField(
        max_length=10,
        default="NGN",
    )

    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
    )

    pricing_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    ai_analysis = models.JSONField(
        default=dict,
        blank=True,
    )

    change_summary = models.TextField(
        blank=True,
        help_text="What changed from the previous version.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-version"]

        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "version"],
                name="unique_proposal_revision_version",
            )
        ]

    def __str__(self):
        return f"{self.proposal.title} - v{self.version}"
    



class ProposalFeature(models.Model):

    SCOPE_STATUS_CHOICES = [
        ("required", "Required"),
        ("recommended", "Recommended"),
        ("optional", "Optional"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("removed", "Removed"),
    ]

    SOURCE_CHOICES = [
        ("ai", "AI"),
        ("client", "Client"),
        ("admin", "Admin"),
    ]

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="proposal_features",
    )

    feature_key = models.CharField(
        max_length=100,
    )

    name = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
    )

    category = models.CharField(
        max_length=100,
        blank=True,
    )
    is_included = models.BooleanField(default=False)

    complexity = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        default="medium",
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    # ---------------------------------------------------------
    # WHAT KIND OF SCOPE IS THIS?
    # ---------------------------------------------------------

    scope_status = models.CharField(
        max_length=20,
        choices=SCOPE_STATUS_CHOICES,
        default="required",
    )

    # ---------------------------------------------------------
    # LIFECYCLE STATE
    # ---------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="approved",
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="ai",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "sort_order",
            "created_at",
        ]

    def __str__(self):
        return self.name
    


    
class ProposalRequirement(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="requirements"
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    requirement_type = models.CharField(
        max_length=30,
        choices=[
            ("confirmed", "Confirmed"),
            ("recommended", "Recommended"),
            ("optional", "Optional"),
            ("future", "Future"),
        ]
    )

    status = models.CharField(
        max_length=30,
        default="pending"
    )

    source = models.CharField(
        max_length=20,
        choices=[
            ("ai", "AI"),
            ("client", "Client"),
            ("admin", "Admin"),
        ],
        default="ai"
    )

    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class ProposalScreen(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="screens",
    )

    name = models.CharField(max_length=255)

    screen_type = models.CharField(
        max_length=100,
        blank=True,
    )

    purpose = models.TextField(blank=True)

    user_roles = models.JSONField(default=list)

    key_functionality = models.JSONField(default=list)

    major_components = models.JSONField(default=list)

    data_involved = models.JSONField(default=list)

    actions = models.JSONField(default=list)

    complexity = models.CharField(
        max_length=30,
        blank=True,
    )

    dependencies = models.JSONField(default=list)

    status = models.CharField(
        max_length=30,
        default="confirmed",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "sort_order",
            "created_at",
        ]

    def __str__(self):
        return self.name
    


class ProposalComment(models.Model):
    ACTION_CHOICES = [
        ("comment", "Comment"),
        ("accept", "Acceptance"),
        ("decline", "Decline"),
    ]

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    milestone_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Milestone ID when this comment belongs to a specific milestone.",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    message = models.TextField()

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default="comment",
    )

    author_type = models.CharField(
        max_length=20,
        choices=[
            ("client", "Client"),
            ("admin", "Admin"),
        ],
        default="client",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.proposal.title} - {self.action}"
    



class ProposalUpdate(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="project_updates",
    )

    milestone_id = models.IntegerField(
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposal_updates",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.proposal.title} - {self.title}"
    






class ProposalUpdateFile(models.Model):
    update = models.ForeignKey(
        ProposalUpdate,
        on_delete=models.CASCADE,
        related_name="files",
    )

    file = models.FileField(
        upload_to="projects/updates/"
    )

    original_name = models.CharField(
        max_length=255,
        blank=True,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.original_name or self.file.name
    










import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class ProposalPayment(models.Model):
    """
    A financial transaction made toward a Proposal.

    One Proposal can have multiple payments.

    Examples:
        Project:
            ₦2,000,000 proposal
            ₦500,000 deposit
            ₦1,500,000 balance

        Procurement:
            ₦10,000,000 proposal
            ₦4,000,000 deposit
            ₦6,000,000 balance

        Training:
            ₦300,000 proposal
            ₦300,000 full payment
    """

    PAYMENT_TYPE_CHOICES = [
        ("deposit", "Deposit"),
        ("partial", "Partial Payment"),
        ("balance", "Balance Payment"),
        ("full", "Full Payment"),
        ("other", "Other"),
    ]

    PROVIDER_CHOICES = [
        ("paystack", "Paystack"),
        ("flutterwave", "Flutterwave"),
        ("bank_transfer", "Bank Transfer"),
        ("manual", "Manual"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("successful", "Successful"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
        ("partially_refunded", "Partially Refunded"),
    ]

    REFUND_STATUS_CHOICES = [
        ("none", "No Refund"),
        ("partial", "Partially Refunded"),
        ("full", "Fully Refunded"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # =========================================================
    # PROPOSAL
    # =========================================================

    proposal = models.ForeignKey(
        "proposals.Proposal",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    milestone = models.ForeignKey(
    "proposals.ProposalMilestone",
    on_delete=models.PROTECT,
    related_name="payments",
    null=True,
    blank=True,
)

    # =========================================================
    # PAYMENT CLASSIFICATION
    # =========================================================

    payment_type = models.CharField(
        max_length=30,
        choices=PAYMENT_TYPE_CHOICES,
        default="partial",
    )

    provider = models.CharField(
        max_length=30,
        choices=PROVIDER_CHOICES,
    )

    # =========================================================
    # MONEY
    # =========================================================

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )

    currency = models.CharField(
        max_length=10,
    )

    # =========================================================
    # PAYMENT STATUS
    # =========================================================

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending",
    )

    # =========================================================
    # REFERENCES
    # =========================================================

    transaction_reference = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
    )

    provider_reference = models.CharField(
        max_length=255,
        blank=True,
    )

    # =========================================================
    # PROVIDER DATA
    # =========================================================

    provider_response = models.JSONField(
        default=dict,
        blank=True,
    )

    # =========================================================
    # REFUNDS
    # =========================================================

    refund_status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default="none",
    )

    refunded_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =========================================================
    # PAYMENT TIMING
    # =========================================================

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =========================================================
    # AUDIT
    # =========================================================

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_proposal_payments",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
            fields=[
                "proposal",
                "status",
            ],
        ),

            models.Index(
            fields=[
                "milestone",
                "status",
            ],
        ),

            models.Index(
            fields=[
                "transaction_reference",
            ],
        ),

            models.Index(
            fields=[
                "provider_reference",
            ],
        ),
    ]

    def __str__(self):
        return (
            f"{self.transaction_reference} - "
            f"{self.proposal.title} - "
            f"{self.currency} {self.amount:,.2f}"
        )

    # =========================================================
    # REFERENCE
    # =========================================================

    @staticmethod
    def generate_transaction_reference():
        """
        Generate a unique AB Technologies payment reference.

        Example:
            AB-PAY-7F3A91C2D8
        """
        return f"AB-PAY-{uuid.uuid4().hex[:10].upper()}"

    def save(self, *args, **kwargs):
        """
        Generate the payment reference once.

        Also copy the proposal currency when a new payment
        is created unless a currency was explicitly supplied.
        """

        if not self.transaction_reference:
            self.transaction_reference = (
                self.generate_transaction_reference()
            )

        if not self.currency and self.proposal:
            self.currency = self.proposal.currency

        super().save(*args, **kwargs)

    # =========================================================
    # STATUS HELPERS
    # =========================================================

    @property
    def is_successful(self):
        return self.status == "successful"

    @property
    def is_refunded(self):
        return self.refund_status == "full"

    @property
    def refundable_amount(self):
        return max(
            Decimal("0.00"),
            self.amount - self.refunded_amount,
        )

    @property
    def formatted_amount(self):
        return f"{self.currency} {self.amount:,.2f}"

    # =========================================================
    # MARK SUCCESSFUL
    # =========================================================

    def mark_successful(
        self,
    provider_reference=None,
    provider_response=None,
    ):
        """
    Mark this payment as successfully completed.

    This should only be called after the payment
    provider has verified the transaction.
        """

        if self.status == "successful":
            return

        self.status = "successful"

        if provider_reference:
            self.provider_reference = (
            provider_reference
            )

        if provider_response is not None:
            self.provider_response = (
            provider_response
        )

        if not self.paid_at:
            self.paid_at = timezone.now()

        self.save(
        update_fields=[
            "status",
            "provider_reference",
            "provider_response",
            "paid_at",
            "updated_at",
            ]
        )

    # =========================================================
    # MARK FAILED
    # =========================================================

    def mark_failed(
        self,
        provider_response=None,
    ):
        self.status = "failed"

        if provider_response is not None:
            self.provider_response = provider_response

        self.save(
            update_fields=[
                "status",
                "provider_response",
                "updated_at",
            ]
        )

    # =========================================================
    # REFUND
    # =========================================================

    def apply_refund(self, amount):
        """
        Record a full or partial refund.

        Refund amount cannot exceed the amount actually paid
        and cannot exceed the remaining refundable amount.
        """

        amount = Decimal(str(amount))

        if amount <= Decimal("0.00"):
            raise ValueError(
                "Refund amount must be greater than zero."
            )

        if self.status != "successful":
            raise ValueError(
                "Only successful payments can be refunded."
            )

        if amount > self.refundable_amount:
            raise ValueError(
                "Refund amount exceeds the refundable balance."
            )

        self.refunded_amount += amount

        if self.refunded_amount >= self.amount:
            self.refunded_amount = self.amount
            self.refund_status = "full"
            self.status = "refunded"
        else:
            self.refund_status = "partial"
            self.status = "partially_refunded"

        self.refunded_at = timezone.now()

        self.save(
            update_fields=[
                "refunded_amount",
                "refund_status",
                "status",
                "refunded_at",
                "updated_at",
            ]
        )





# proposals/models.py

import uuid
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator


class ProposalMilestone(models.Model):

    STATUS_CHOICES = [
        ("locked", "Locked"),
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("not_required", "Not Required"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    proposal = models.ForeignKey(
        "proposals.Proposal",
        on_delete=models.CASCADE,
        related_name="milestone_records",
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.00")
            )
        ],
    )

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    payment_required = models.BooleanField(
        default=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="locked",
    )

    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    deliverables = models.JSONField(
        default=list,
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "proposal",
                    "order",
                ]
            ),
            models.Index(
                fields=[
                    "proposal",
                    "payment_status",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.proposal.title} - "
            f"{self.order}. {self.title}"
        )

  
    @property
    def total_paid(self):
        total = Decimal("0.00")

        payments = self.payments.filter(
            status__in=[
                "successful",
                "partially_refunded",
            ]
        )

        for payment in payments:
            amount = (
                payment.amount
                or Decimal("0.00")
            )

            refunded = (
                payment.refunded_amount
                or Decimal("0.00")
            )

            total += max(
                Decimal("0.00"),
                amount - refunded,
            )

        return max(
            Decimal("0.00"),
            total,
        )

    @property
    def outstanding_balance(self):
        return max(
            Decimal("0.00"),
            (
                self.amount
                or Decimal("0.00")
            )
            - self.total_paid,
        )

    @property
    def is_paid(self):
        if not self.payment_required:
            return False

        return (
            self.outstanding_balance
            <= Decimal("0.00")
        )

    @property
    def is_payable(self):
        if not self.payment_required:
            return False

        if self.status in {
            "locked",
            "cancelled",
        }:
            return False

        if self.is_paid:
            return False

        return True

    @property
    def formatted_amount(self):
        return (
            f"{self.proposal.currency} "
            f"{self.amount:,.2f}"
        )

    @property
    def formatted_total_paid(self):
        return (
            f"{self.proposal.currency} "
            f"{self.total_paid:,.2f}"
        )

    @property
    def formatted_outstanding(self):
        return (
            f"{self.proposal.currency} "
            f"{self.outstanding_balance:,.2f}"
        )