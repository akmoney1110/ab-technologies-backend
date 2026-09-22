from django.conf import settings
from django.db import models

from django.core.validators import MaxValueValidator
class Project(models.Model):

    class Status(models.TextChoices):
        PLANNING = "PLANNING", "Planning"
        ACTIVE = "ACTIVE", "Active"
        ON_HOLD = "ON_HOLD", "On Hold"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    # The client who owns / is associated with this project.
    #
    # This allows individual clients to have projects without
    # requiring an organization.
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_projects",
        null=True,
        blank=True,
    )

    # Optional organization.
    #
    # Individual client:
    #     organization = None
    #
    # Business client:
    #     organization = ABC Technologies
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=255,
    )

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNING,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    progress = models.PositiveIntegerField(
    default=0,
    validators=[
        MaxValueValidator(100),
    ],
)

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    expected_completion_date = models.DateField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_projects",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"
    





# projects/models.py

from django.db import models
from proposals.models import Proposal


class ClientProjectContent(models.Model):
    proposal = models.OneToOneField(
        Proposal,
        on_delete=models.CASCADE,
        related_name="client_content",
    )

    # --------------------------------------------------
    # BRAND
    # --------------------------------------------------

    brand_name = models.CharField(
        max_length=255,
        blank=True,
    )

    tagline = models.CharField(
        max_length=255,
        blank=True,
    )

    primary_color = models.CharField(
        max_length=20,
        blank=True,
        help_text="HEX color, e.g. #1D4ED8",
    )

    secondary_color = models.CharField(
        max_length=20,
        blank=True,
    )

    accent_color = models.CharField(
        max_length=20,
        blank=True,
    )

    background_color = models.CharField(
        max_length=20,
        blank=True,
    )

    text_color = models.CharField(
        max_length=20,
        blank=True,
    )

    font_family = models.CharField(
        max_length=100,
        blank=True,
    )

    # --------------------------------------------------
    # COMPANY / PROJECT INFORMATION
    # --------------------------------------------------

    company_description = models.TextField(
        blank=True,
    )

    about_content = models.TextField(
        blank=True,
    )

    mission = models.TextField(
        blank=True,
    )

    vision = models.TextField(
        blank=True,
    )

    contact_information = models.TextField(
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    phone = models.CharField(
        max_length=100,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    website = models.URLField(
        blank=True,
    )

    # --------------------------------------------------
    # GENERAL CONTENT
    # --------------------------------------------------

    additional_content = models.JSONField(
        default=dict,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    # --------------------------------------------------
    # STATUS
    # --------------------------------------------------

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    reviewed_at = models.DateTimeField(
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
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Client Content - {self.proposal}"
    






class ClientProjectContentFile(models.Model):

    FILE_TYPE_CHOICES = [
        ("logo", "Logo"),
        ("image", "Image"),
        ("document", "Document"),
        ("video", "Video"),
        ("brand_guideline", "Brand Guideline"),
        ("content", "Content"),
        ("other", "Other"),
    ]

    content = models.ForeignKey(
        ClientProjectContent,
        on_delete=models.CASCADE,
        related_name="files",
    )

    file = models.FileField(
        upload_to="projects/client-content/%Y/%m/",
    )

    original_name = models.CharField(
        max_length=255,
    )

    file_type = models.CharField(
        max_length=30,
        choices=FILE_TYPE_CHOICES,
        default="other",
    )

    description = models.CharField(
        max_length=500,
        blank=True,
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.original_name    