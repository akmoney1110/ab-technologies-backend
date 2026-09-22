from django.db import models

# Create your models here.
import uuid

from django.db import models


class Lead(models.Model):

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("converted", "Converted"),
        ("lost", "Lost"),
    ]

    SOURCE_CHOICES = [
        ("ai", "AB AI"),
        ("website", "Website"),
        ("manual", "Manual"),
        ("referral", "Referral"),
        ("other", "Other"),
    ]

    INTENT_CHOICES = [
        ("general", "General Enquiry"),
        ("service", "Service"),
        ("procurement", "Procurement"),
        ("product", "Product"),
        ("training", "Training"),
        ("support", "Support"),
        ("consultation", "Consultation"),
        ("project", "Project"),
        ("other", "Other"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=255,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
    )

    company = models.CharField(
        max_length=255,
        blank=True,
    )

    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="ai",
    )

    intent = models.CharField(
        max_length=30,
        choices=INTENT_CHOICES,
        default="general",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="new",
    )

    notes = models.TextField(
        blank=True,
    )

    conversation = models.ForeignKey(
        "ai.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    country = models.CharField(
    max_length=100,
    blank=True,
    )

    country_code = models.CharField(
    max_length=10,
    blank=True,
    )

    preferred_currency = models.CharField(
    max_length=10,
    blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or self.email or str(self.id)




class QuoteRequest(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("priced", "Priced"),
        ("sent", "Sent"),
        ("negotiation", "Negotiation"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="quote_requests",
    )
    notes = models.TextField(
        blank=True,
    )

    title = models.CharField(max_length=255)
    purpose = models.TextField(blank=True)

    currency = models.CharField(max_length=10, default="NGN")

    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    description = models.TextField(
        blank=True,
    )

    delivery_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProcurementQuotationItem(models.Model):
    quotation = models.ForeignKey(
        QuoteRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )

    category = models.CharField(max_length=100)

    name = models.CharField(max_length=255)

    brand = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    model = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    description = models.TextField(blank=True)

    specifications = models.JSONField(
        default=dict,
        blank=True,
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




class ProjectRequest(models.Model):

    STATUS_CHOICES = [
        ("new", "New"),
        ("reviewing", "Reviewing"),
        ("discovery", "Discovery"),
        ("proposal", "Proposal"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="project_requests",
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
    )

    project_type = models.CharField(
        max_length=100,
        blank=True,
    )

    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    currency = models.CharField(
        max_length=10,
        default="USD",
    )

    deadline = models.DateField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="new",
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SupportTicket(models.Model):

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("waiting", "Waiting"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )

    subject = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="normal",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="open",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.subject
    


def generate_tracking_reference():
    """
    Generate one permanent tracking reference for each procurement.

    Example:
        AB-TRK-7F3A91C2D8
    """
    return f"AB-TRK-{uuid.uuid4().hex[:10].upper()}"




# crm/models.py

import uuid
from decimal import Decimal

from django.db import models


class QuoteRequest(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("priced", "Priced"),
        ("sent", "Sent"),
        ("negotiation", "Negotiation"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    REQUEST_TYPE_CHOICES = [
        ("procurement", "Procurement"),
        ("service", "Service"),
        ("product", "Product"),
        ("mixed", "Mixed"),
        ("other", "Other"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tracking_reference = models.CharField(
        max_length=50,
        unique=True,
       
        blank=True,
        editable=False,
    )

    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.CASCADE,
        related_name="quote_requests",
    )

    title = models.CharField(
        max_length=255,
    )

    request_type = models.CharField(
        max_length=30,
        choices=REQUEST_TYPE_CHOICES,
        default="procurement",
    )

    description = models.TextField(
        blank=True,
    )

    purpose = models.TextField(
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    currency = models.CharField(
        max_length=10,
        default="NGN",
    )

    deadline = models.DateField(
        null=True,
        blank=True,
    )

    # ========================================================
    # PRICING
    # ========================================================

    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    delivery_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # ========================================================
    # AUDIT
    # ========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def formatted_total(self):
        return f"{self.currency} {self.total:,.2f}"
    import uuid


    def generate_tracking_reference():
        return f"AB-TRK-{uuid.uuid4().hex[:10].upper()}"
    def save(self, *args, **kwargs):
        if not self.tracking_reference:
            self.tracking_reference = generate_tracking_reference()

        super().save(*args, **kwargs)

    def calculate_totals(self, save=True):
        """
        Calculate the quotation from its items.

        Django is the source of truth for all monetary calculations.
        """

        items = self.items.all()

        subtotal = Decimal("0.00")
        all_priced = True

        for item in items:
            if item.unit_price is None:
                item.total_price = None
                all_priced = False
                if item.pk:
                    item.save(
                        update_fields=["total_price", "updated_at"]
                    )
                continue

            item.total_price = (
                item.unit_price * item.quantity
            )

            item.save(
                update_fields=[
                    "total_price",
                    "updated_at",
                ]
            )

            subtotal += item.total_price

        self.subtotal = subtotal

        self.total = (
            self.subtotal
            - self.discount
            + self.tax
            + self.delivery_fee
        )

        if items.exists() and all_priced:
            self.status = "priced"
        else:
            self.status = "draft"

        if save:
            self.save(
                update_fields=[
                    "subtotal",
                    "total",
                    "status",
                    "updated_at",
                ]
            )

        return self.total
    


class ProcurementQuotationItem(models.Model):
    quotation = models.ForeignKey(
        QuoteRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )

    category = models.CharField(
        max_length=100,
    )

    name = models.CharField(
        max_length=255,
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    model = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
    )

    specifications = models.JSONField(
        default=dict,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
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
        ordering = ["created_at"]

    def __str__(self):
        parts = [self.name]

        if self.brand:
            parts.append(self.brand)

        if self.model:
            parts.append(self.model)

        return " ".join(parts)

    def calculate_total(self, save=True):
        if self.unit_price is None:
            self.total_price = None
        else:
            self.total_price = (
                self.unit_price * self.quantity
            )

        if save:
            self.save(
                update_fields=[
                    "total_price",
                    "updated_at",
                ]
            )

        return self.total_price



class ProcurementClientRevision(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("reviewed", "Reviewed"),
        ("countered", "Countered"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    quote = models.ForeignKey(
        QuoteRequest,
        on_delete=models.CASCADE,
        related_name="client_revisions",
    )

    revision_number = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    delivery_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    client_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def calculate_totals(self, save=True):
        subtotal = Decimal("0.00")

        items = self.items.all()

        for item in items:
            item_total = item.calculate_total(save=True)

            if not item.removed:
                subtotal += item_total

        self.subtotal = subtotal

        self.total = (
            self.subtotal
            - self.discount
            + self.tax
            + self.delivery_fee
        )

        if save:
            self.save(
                update_fields=[
                "subtotal",
                "total",
                "updated_at",
            ]
        )

        return self.total

class ProcurementClientRevisionItem(models.Model):
    revision = models.ForeignKey(
        ProcurementClientRevision,
        on_delete=models.CASCADE,
        related_name="items",
    )

    quotation_item = models.ForeignKey(
        ProcurementQuotationItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_revision_items",
    )

    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True)

    description = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)

    quantity = models.PositiveIntegerField(default=1)

    # Original price supplied by AB Technologies
    quoted_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    # Price proposed by client during negotiation
    proposed_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Price finally approved by AB Technologies
    approved_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    removed = models.BooleanField(default=False)

    client_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.name

    @property
    def effective_unit_price(self):
        return (
            self.approved_unit_price
            if self.approved_unit_price is not None
            else self.proposed_unit_price
            if self.proposed_unit_price is not None
            else self.quoted_unit_price
        )

    def calculate_total(self, save=True):
        if self.removed:
            self.total_price = Decimal("0.00")
        else:
            self.total_price = (
                self.effective_unit_price * self.quantity
            )

        if save:
            self.save(
                update_fields=[
                    "total_price",
                    "updated_at",
                ]
            )

        return self.total_price