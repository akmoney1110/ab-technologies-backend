from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models


class Organization(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        PROSPECT = "PROSPECT", "Prospect"

    name = models.CharField(max_length=255)

    legal_name = models.CharField(
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

    address = models.TextField(
        blank=True,
    )

    website = models.URLField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_created",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name
    



class OrganizationMember(models.Model):

    class MemberRole(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        MEMBER = "MEMBER", "Member"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
        default=MemberRole.MEMBER,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_member",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.organization}"    