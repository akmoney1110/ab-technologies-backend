from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Organization, OrganizationMember


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "legal_name",
        "email",
        "phone",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "name",
        "legal_name",
        "email",
        "phone",
    )


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "user",
        "role",
        "is_active",
        "created_at",
    )

    list_filter = (
        "role",
        "is_active",
    )

    search_fields = (
        "organization__name",
        "user__email",
        "user__first_name",
        "user__last_name",
    )