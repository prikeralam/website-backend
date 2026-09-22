import django_filters
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .models import Theme
from .permissions import IsStaffOrReadOnly
from .serializers import SubThemeSerializer, ThemeSerializer

TAXONOMY_TAG = "Shared — Taxonomy"


class ThemeFilter(django_filters.FilterSet):
    parent = django_filters.NumberFilter(field_name="parent_id")
    top_level = django_filters.BooleanFilter(field_name="parent", lookup_expr="isnull")

    class Meta:
        model = Theme
        fields = ["parent", "top_level"]


@extend_schema(tags=[TAXONOMY_TAG])
class ThemeViewSet(ModelViewSet):
    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    filterset_class = ThemeFilter


@extend_schema(tags=[TAXONOMY_TAG])
class SubThemeViewSet(ModelViewSet):
    """Nested under /themes/{theme_pk}/subthemes/ — a dedicated CRUD surface for
    sub-themes of one specific top-level theme, on top of the flat /themes/?parent=
    filter ThemeViewSet already supports."""

    serializer_class = SubThemeSerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def get_parent_theme(self):
        # parent__isnull=True: theme_pk must itself be a top-level theme — creating a
        # subtheme under another subtheme would violate the 2-level cap (Theme.clean()).
        return get_object_or_404(Theme, pk=self.kwargs["theme_pk"], parent__isnull=True)

    def get_queryset(self):
        return Theme.objects.filter(parent_id=self.kwargs["theme_pk"])

    def perform_create(self, serializer):
        serializer.save(parent=self.get_parent_theme())
