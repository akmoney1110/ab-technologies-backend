from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models


class ProcurementRequest(models.Model):

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        QUOTED = "QUOTED", "Quoted"
        APPROVED = "APPROVED", "Approved"
        ORDERED = "ORDERED", "Ordered"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="procurement_requests",
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    estimated_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_procurements",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title
    




# procurement/models.py
# or crm/models.py, wherever your procurement models live
from django.conf import settings
from django.db import models
from django.utils import timezone


class ProcurementTrackingUpdate(models.Model):

    STATUS_CHOICES = [
        ("order_confirmed", "Order Confirmed"),
        ("supplier_confirmed", "Supplier Confirmed"),
        ("order_placed", "Order Placed"),
        ("processing", "Processing"),
        ("ready_for_dispatch", "Ready for Dispatch"),
        ("dispatched", "Dispatched"),
        ("in_transit", "In Transit"),
        ("arrived", "Arrived"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("on_hold", "On Hold"),
        ("delayed", "Delayed"),
        ("cancelled", "Cancelled"),
    ]

    quotation = models.ForeignKey(
        "crm.QuoteRequest",
        on_delete=models.CASCADE,
        related_name="tracking_updates",
    )

    

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
    )

    title = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    location = models.CharField(
        max_length=255,
        blank=True,
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procurement_tracking_updates",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.quotation.title} - "
            f"{self.get_status_display()}"
        )

    