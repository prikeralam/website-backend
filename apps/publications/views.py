from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import Publication
from .serializers import PublicationSerializer


class PublicationViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Publication.objects.all()
    serializer_class = PublicationSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["format", "theme", "language", "status"]
