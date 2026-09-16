from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import ContentBlock, Document, PersonProfile, Testimonial
from .serializers import (
    ContentBlockSerializer,
    DocumentSerializer,
    PersonProfileSerializer,
    TestimonialSerializer,
)


class ContentBlockViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = ContentBlock.objects.all()
    serializer_class = ContentBlockSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]


class TestimonialViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Testimonial.objects.all()
    serializer_class = TestimonialSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]


class PersonProfileViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = PersonProfile.objects.all()
    serializer_class = PersonProfileSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]


class DocumentViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
