from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import WorkflowStatus

CONTRIBUTOR_ROLES = {"researcher", "editor", "admin"}
STAFF_ROLES = {"editor", "admin"}


def _role(request):
    return getattr(request.user, "role", None)


class CanSubmitDraft(BasePermission):
    """
    Create (POST): allowed for contributor roles (researcher, editor, admin).
    Update (PATCH/PUT) while the object is still `draft`: allowed for the
    object's own creator (any contributor role) OR for editor/admin.
    Update of an object past `draft`: restricted to editor/admin.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return _role(request) in CONTRIBUTOR_ROLES
        # PUT/PATCH/DELETE are resolved at the object level.
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        role = _role(request)

        if request.method in ("PUT", "PATCH"):
            if obj.status == WorkflowStatus.DRAFT:
                return obj.created_by_id == request.user.id or role in STAFF_ROLES
            return role in STAFF_ROLES

        if request.method == "DELETE":
            return role in STAFF_ROLES

        return False


class CanTransitionStatus(BasePermission):
    """
    Used on the shared `transition` action.
    draft -> in_review: allowed for the object's own creator with a
    contributor role, OR for editor/admin.
    Any other transition: allowed only for editor/admin.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        role = _role(request)
        target_status = request.data.get("status")

        if obj.status == WorkflowStatus.DRAFT and target_status == WorkflowStatus.IN_REVIEW:
            is_own_contributor = obj.created_by_id == request.user.id and role in CONTRIBUTOR_ROLES
            return is_own_contributor or role in STAFF_ROLES

        return role in STAFF_ROLES
