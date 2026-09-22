from django.contrib import admin

# Register your models here.

from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    # =========================================================
    # LIST DISPLAY
    # =========================================================

    list_display = (
        "code",
        "name",
        "client",
        "organization",
        "status",
        "priority",
        "progress_display",
        "manager",
        "start_date",
        "expected_completion_date",
        "updated_at",
    )

    # =========================================================
    # SEARCH
    # =========================================================

    search_fields = (
        "code",
        "name",
        "description",
        "client__email",
        "client__first_name",
        "client__last_name",
        "organization__name",
        "manager__email",
        "manager__first_name",
        "manager__last_name",
    )

    # =========================================================
    # FILTERS
    # =========================================================

    list_filter = (
        "status",
        "priority",
        "organization",
        "start_date",
        "expected_completion_date",
        "created_at",
        "updated_at",
    )

    # =========================================================
    # DATE NAVIGATION
    # =========================================================

    date_hierarchy = "created_at"

    # =========================================================
    # DEFAULT ORDERING
    # =========================================================

    ordering = (
        "-updated_at",
    )

    # =========================================================
    # ITEMS PER PAGE
    # =========================================================

    list_per_page = 25

    # =========================================================
    # EDIT FORM
    # =========================================================

    fieldsets = (
        (
            "Project Information",
            {
                "fields": (
                    "name",
                    "code",
                    "description",
                )
            },
        ),

        (
            "Client",
            {
                "fields": (
                    "client",
                    "organization",
                ),
                "description": (
                    "For an individual client, select the client "
                    "and leave Organization empty. For a business "
                    "client, select both the client and their "
                    "organization."
                ),
            },
        ),

        (
            "Project Status",
            {
                "fields": (
                    "status",
                    "priority",
                    "progress",
                )
            },
        ),

        (
            "Schedule",
            {
                "fields": (
                    "start_date",
                    "expected_completion_date",
                    "completed_at",
                )
            },
        ),

        (
            "Assignment",
            {
                "fields": (
                    "manager",
                )
            },
        ),

        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    # =========================================================
    # READ-ONLY SYSTEM FIELDS
    # =========================================================

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    # =========================================================
    # PROGRESS DISPLAY
    # =========================================================

    @admin.display(
        description="Progress",
        ordering="progress",
    )
    def progress_display(self, obj):
        return f"{obj.progress}%"

    # =========================================================
    # AUTOCOMPLETE
    # =========================================================

    autocomplete_fields = (
        "client",
        "organization",
        "manager",
    )

