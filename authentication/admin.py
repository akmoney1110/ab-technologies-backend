from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    ordering = ("email",)

    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "is_active",
        "is_staff",
        "date_joined",
    )

    list_filter = (
        "role",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
        "phone",
    )

    readonly_fields = (
        "date_joined",
        "updated_at",
    )

    fieldsets = (
        (
            "Login Information",
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "address",
                )
            },
        ),
        (
            "Access & Role",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "date_joined",
                    "updated_at",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            "Create User",
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "address",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )