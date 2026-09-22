from django.db import models

# Create your models here.
class Invoice(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"
        CANCELLED = "CANCELLED", "Cancelled"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,
        blank=True,
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
    )

    title = models.CharField(
        max_length=255,
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )