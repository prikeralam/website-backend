from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import Project
from .serializers import ProjectSerializer


@extend_schema(tags=["Projects (Homepage)"])
class ProjectViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
