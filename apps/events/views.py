from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import AuditLog
from apps.workflow.models import WorkflowStatus
from apps.workflow.permissions import CONTRIBUTOR_ROLES, STAFF_ROLES, CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import Event, EventImage
from .serializers import EventImageSerializer, EventSerializer

MODULE_TAG = "Events & Campaigns"


def can_edit_event(user, event):
    """Who may change an event's photos: the same rule as editing it (CanSubmitDraft), i.e. its contributor creator
    while it is a draft, and editors and admins always."""
    role = getattr(user, "role", None)
    if role in STAFF_ROLES:
        return True
    return role in CONTRIBUTOR_ROLES and event.status == WorkflowStatus.DRAFT and event.created_by_id == user.id


@extend_schema(tags=[MODULE_TAG])
class EventViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Event.objects.prefetch_related("images")
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
    filterset_fields = ["kind"]

    def get_permissions(self):
        if self.action in ("add_image", "remove_image"):
            # Decided per event by can_edit_event (see _editable_event).
            return [IsAuthenticated()]
        return super().get_permissions()

    def _editable_event(self, request):
        event = self.get_object()
        if not can_edit_event(request.user, event):
            self.permission_denied(request, message="You can't change this event's photos.")
        return event

    @extend_schema(request={"multipart/form-data": EventImageSerializer}, responses={201: EventImageSerializer})
    @action(detail=True, methods=["post"], url_path="images")
    def add_image(self, request, slug=None):
        """Add a photo to the event's gallery (JPG, PNG or WebP up to 5 MB, optional caption)."""
        event = self._editable_event(request)
        if event.images.count() >= EventImage.MAX_PER_EVENT:
            return Response(
                {"detail": f"An event can have up to {EventImage.MAX_PER_EVENT} photos. Remove one first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = EventImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        last = event.images.order_by("-display_order").first()
        photo = serializer.save(event=event, display_order=(last.display_order + 1) if last else 0)
        AuditLog.objects.create(
            actor=request.user,
            module="events",
            action="event_image_added",
            target=f"event:{event.pk}",
            metadata={"image_id": photo.pk},
        )
        return Response(EventImageSerializer(photo, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def remove_image(self, request, slug=None, image_id=None):
        """Remove one gallery photo; its stored file is deleted too."""
        event = self._editable_event(request)
        photo = EventImage.objects.filter(event=event, pk=image_id).first()
        if photo is None:
            return Response({"detail": "No such photo on this event."}, status=status.HTTP_404_NOT_FOUND)
        AuditLog.objects.create(
            actor=request.user,
            module="events",
            action="event_image_removed",
            target=f"event:{event.pk}",
            metadata={"image_id": photo.pk},
        )
        photo.image.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
