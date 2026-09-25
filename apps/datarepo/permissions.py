"""Three-tier dataset visibility enforcement — see docs/api/module-c-data-repository.md
and docs/PRDs/C-data-repository-dashboard-integration.md:36-39.

    public         - visible to anyone, including anonymous visitors, once published.
    on_request     - listed for everyone, but full download requires an approved
                     AccessRequest for that user (or staff).
    internal_only  - excluded entirely from any non-staff (non researcher/editor/admin)
                     response — not just download-gated, genuinely invisible.
"""
from apps.workflow.permissions import STAFF_ROLES

INTERNAL_USE_ROLES = STAFF_ROLES | {"researcher"}


def _role(user):
    return getattr(user, "role", None)


def visible_datasets_for(user, queryset):
    """Datasets that should appear in list/detail/preview responses for this user."""
    if _role(user) in INTERNAL_USE_ROLES:
        return queryset
    return queryset.exclude(visibility="internal_only")


def can_download(user, dataset):
    role = _role(user)
    if dataset.visibility == "internal_only":
        # PRD C line 39: internal_only exists for Admin/Editor/Researcher-authenticated
        # internal use — the same role group that can see it can also download it.
        return role in INTERNAL_USE_ROLES
    if role in STAFF_ROLES:
        return True
    if dataset.visibility == "public":
        return True
    # on_request: an approved request belongs to a signed-in user, so anonymous visitors never qualify
    if not user.is_authenticated:
        return False
    return dataset.access_requests.filter(user=user, status="approved").exists()
