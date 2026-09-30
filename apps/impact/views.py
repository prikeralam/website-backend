from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.viewsets import ModelViewSet

from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import Mention, Recognition
from .serializers import MentionSerializer, RecognitionSerializer

MODULE_TAG = "Impact (Cited in & Recognition)"


@extend_schema(tags=[MODULE_TAG])
class MentionViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Mention.objects.select_related("publication", "dataset")
    serializer_class = MentionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
    filterset_fields = ["kind"]


@extend_schema(tags=[MODULE_TAG])
class RecognitionViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Recognition.objects.all()
    serializer_class = RecognitionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
