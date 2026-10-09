from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import WorkflowStatus
from .permissions import CanTransitionStatus, visible_workflow_objects
from .serializers import TransitionSerializer


class WorkflowViewSetMixin:
    """
    Mixin for any content-type ViewSet built on WorkflowMixin models.
    Provides a shared `POST /<resource>/<pk>/transition/` action that
    validates the target status, applies role-gated permission checks,
    updates the object, and writes an AuditLog row.
    """

    def get_queryset(self):
        return visible_workflow_objects(self.request.user, super().get_queryset())

    def get_permissions(self):
        if self.action == "transition":
            return [IsAuthenticated(), CanTransitionStatus()]
        return super().get_permissions()

    def publish_blocker(self, obj):
        """Why `obj` can't be published yet, or None. Content types with publishing requirements override this."""
        return None

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, *args, **kwargs):
        # Imported here (not at module level) to avoid a circular import:
        # apps.accounts never imports apps.workflow, so this is safe at
        # call time even though workflow is a lower-level/shared app.
        from apps.accounts.models import AuditLog

        obj = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_status = serializer.validated_data["status"]
        previous_status = obj.status
        if target_status == WorkflowStatus.PUBLISHED:
            blocker = self.publish_blocker(obj)
            if blocker:
                return Response({"detail": blocker}, status=status.HTTP_400_BAD_REQUEST)

        update_fields = ["status", "reviewed_by", "updated_at"]
        obj.status = target_status
        obj.reviewed_by = request.user
        if target_status == WorkflowStatus.PUBLISHED:
            obj.published_at = timezone.now()
            update_fields.append("published_at")
        obj.save(update_fields=update_fields)

        AuditLog.objects.create(
            actor=request.user,
            module=getattr(self, "basename", self.__class__.__name__.lower()),
            action="status_transition",
            target=f"{obj.__class__.__name__.lower()}:{obj.pk}",
            metadata={"previous_status": previous_status, "new_status": target_status},
        )

        return Response(self.get_serializer(obj).data)
