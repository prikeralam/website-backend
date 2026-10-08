from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.viewsets import ModelViewSet

from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import Event
from .serializers import EventSerializer

MODULE_TAG = "Events & Campaigns"


@extend_schema(tags=[MODULE_TAG])
class EventViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
    filterset_fields = ["kind"]
