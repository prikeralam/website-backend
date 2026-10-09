import django_filters
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.workflow.permissions import STAFF_ROLES, CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .citations import FORMATTERS
from .models import Publication, PublicationVersion
from .serializers import PublicationSerializer, PublicationVersionSerializer


class PublicationFilter(django_filters.FilterSet):
    # `theme` filters by the top-level theme (via the linked sub_theme's parent) — lets a
    # caller find every publication under e.g. "Education" without knowing each sub-theme id.
    theme = django_filters.NumberFilter(field_name="sub_theme__parent_id")

    class Meta:
        model = Publication
        # "theme" isn't a real model field — it's the explicitly declared filter above;
        # explicitly declared filters don't need (and shouldn't get) a Meta.fields entry,
        # since Meta.fields is only for deriving auto-generated filters from real fields.
        fields = ["format", "sub_theme", "language", "status"]


@extend_schema(tags=["Module B — Publications"])
class PublicationViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Publication.objects.all()
    serializer_class = PublicationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PublicationFilter
    search_fields = ["title", "abstract"]

    def publish_blocker(self, obj):
        # Every publication appears as a card on the research hub, which needs a real image.
        if not (obj.cover or obj.cover_url):
            return "Add a cover image before publishing. It is shown on the publication's card in the research list."
        return None

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", None) not in STAFF_ROLES:
            visible = ~Q(visibility="private")
            if user.is_authenticated:
                visible |= Q(created_by=user)
            queryset = queryset.filter(visible)
        return queryset

    def filter_queryset(self, queryset):
        # DjangoFilterBackend/SearchFilter are for the list action only — applying them to
        # detail lookups would let a query param like citation's own `?format=` collide with
        # the model's `format` filterset field (django-filter would filter out any publication
        # whose format != the requested citation format, 404ing every citation request).
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    @action(detail=True, methods=["post"])
    def versions(self, request, slug=None):
        publication = self.get_object()
        serializer = PublicationVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_current = serializer.validated_data.get("is_current", True)
        if is_current:
            PublicationVersion.objects.filter(publication=publication, is_current=True).update(is_current=False)

        version = serializer.save(publication=publication, uploaded_by=request.user, is_current=is_current)
        return Response(PublicationVersionSerializer(version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, slug=None):
        publication = self.get_object()
        version_number = request.query_params.get("version")
        if version_number:
            version = get_object_or_404(
                PublicationVersion, publication=publication, version_number=version_number
            )
        else:
            version = publication.versions.filter(is_current=True).first()
            if version is None:
                return Response({"detail": "No file has been uploaded for this publication."}, status=404)
        return Response({"file": request.build_absolute_uri(version.file.url)})

    @action(detail=True, methods=["get"])
    def citation(self, request, slug=None):
        publication = self.get_object()
        citation_format = request.query_params.get("format", "apa")
        formatter = FORMATTERS.get(citation_format)
        if formatter is None:
            return Response(
                {"detail": f"Unsupported citation format '{citation_format}'. Use one of: {', '.join(FORMATTERS)}."},
                status=400,
            )
        return HttpResponse(formatter(publication), content_type="text/plain")
