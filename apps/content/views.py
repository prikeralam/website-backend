from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.workflow.models import WorkflowStatus
from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import ContentBlock, Document, PersonProfile, Testimonial
from .serializers import (
    ContentBlockSerializer,
    DocumentSerializer,
    LatestUpdateItemSerializer,
    PersonProfileSerializer,
    TestimonialSerializer,
)

MODULE_TAG = "Module A — Content"


@extend_schema(tags=[MODULE_TAG])
class ContentBlockViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = ContentBlock.objects.all()
    serializer_class = ContentBlockSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
    lookup_field = "slug"


@extend_schema(tags=[MODULE_TAG])
class TestimonialViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Testimonial.objects.all()
    serializer_class = TestimonialSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]


@extend_schema(tags=[MODULE_TAG])
class PersonProfileViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = PersonProfile.objects.all()
    serializer_class = PersonProfileSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["group"]


@extend_schema(tags=[MODULE_TAG])
class DocumentViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["document_type", "year"]


# Module A's own content types only (ContentBlock/Testimonial/PersonProfile/Document) —
# Publications (Module B) and Projects are out of this cross-type feed's documented scope.
_LATEST_UPDATES_TYPES = {
    "content-block": (ContentBlock, "title"),
    "testimonial": (Testimonial, "attribution"),
    "person": (PersonProfile, "name"),
    "document": (Document, "title"),
}


class LatestUpdatesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[MODULE_TAG],
        responses=LatestUpdateItemSerializer(many=True),
        parameters=[
            OpenApiParameter("types", str, description="Comma-separated: content-block,testimonial,person,document"),
            OpenApiParameter("limit", int, description="Max items to return (default 20, max 100)"),
        ],
    )
    def get(self, request):
        requested_types = request.query_params.get("types")
        type_keys = (
            [t.strip() for t in requested_types.split(",") if t.strip()]
            if requested_types
            else list(_LATEST_UPDATES_TYPES)
        )
        try:
            limit = int(request.query_params.get("limit", 20))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 100))

        items = []
        for type_key in type_keys:
            entry = _LATEST_UPDATES_TYPES.get(type_key)
            if entry is None:
                continue
            model, title_field = entry
            queryset = model.objects.filter(
                status=WorkflowStatus.PUBLISHED, published_at__isnull=False
            ).order_by("-published_at")[:limit]
            for obj in queryset:
                items.append(
                    {
                        "type": type_key,
                        "id": obj.pk,
                        "slug": obj.slug,
                        "title": getattr(obj, title_field),
                        "published_at": obj.published_at,
                    }
                )

        items.sort(key=lambda item: item["published_at"], reverse=True)
        return Response(LatestUpdateItemSerializer(items[:limit], many=True).data)
