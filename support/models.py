from django.db import models
from django.conf import settings
# Create your models here.
class SupportTicket(models.Model):

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        WAITING = "WAITING", "Waiting for Client"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="support_tickets",
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_support_tickets",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )