from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import CanTransitionStatus
from .serializers import TransitionSerializer


class WorkflowViewSetMixin:
    """
    Mixin for any content-type ViewSet built on WorkflowMixin models.
    Provides a shared `POST /<resource>/<pk>/transition/` action that
    validates the target status, applies role-gated permission checks,
    updates the object, and writes an AuditLog row.
    """

    def get_permissions(self):
        if self.action == "transition":
            return [IsAuthenticated(), CanTransitionStatus()]
        return super().get_permissions()

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        # Imported here (not at module level) to avoid a circular import:
        # apps.accounts never imports apps.workflow, so this is safe at
        # call time even though workflow is a lower-level/shared app.
        from apps.accounts.models import AuditLog

        obj = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_status = serializer.validated_data["status"]
        previous_status = obj.status

        obj.status = target_status
        obj.reviewed_by = request.user
        obj.save(update_fields=["status", "reviewed_by", "updated_at"])

        AuditLog.objects.create(
            actor=request.user,
            module=getattr(self, "basename", self.__class__.__name__.lower()),
            action="status_transition",
            target=f"{obj.__class__.__name__.lower()}:{obj.pk}",
            metadata={"previous_status": previous_status, "new_status": target_status},
        )

        return Response(self.get_serializer(obj).data)
