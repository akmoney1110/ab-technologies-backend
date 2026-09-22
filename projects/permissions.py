from rest_framework.permissions import BasePermission


class IsStaffOrAdmin(BasePermission):
    """
    Allows AB Technologies staff/admin users to manage projects.

    Supports:
    - Django is_staff / is_superuser
    - Custom role fields such as ADMIN, MANAGER, STAFF
    """

    message = "You do not have permission to manage projects."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if getattr(user, "is_superuser", False):
            return True

        if getattr(user, "is_staff", False):
            return True

        role = getattr(user, "role", None)

        if role:
            role = str(role).upper()

        return role in {
            "ADMIN",
            "MANAGER",
            "STAFF",
        }