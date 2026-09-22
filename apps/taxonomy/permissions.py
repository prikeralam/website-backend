from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.workflow.permissions import STAFF_ROLES


class IsStaffOrReadOnly(BasePermission):
    """Theme is shared reference data used across Modules B/C — read for any authenticated
    user, write (create/update/delete) restricted to editor/admin, same as who can approve/
    publish workflowed content, rather than opened up to every contributor role."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.role in STAFF_ROLES)
