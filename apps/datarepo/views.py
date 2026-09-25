import django_filters
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import AuditLog
from apps.workflow.permissions import STAFF_ROLES, CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import AccessRequest, Dashboard, Dataset
from .permissions import can_download, visible_datasets_for
from .previews import PreviewError, UnsupportedFormat, table_page
from .serializers import AccessRequestReviewSerializer, AccessRequestSerializer, DashboardSerializer, DatasetSerializer

MODULE_TAG = "Module C — Data Repository"


class IsStaffRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in STAFF_ROLES)


class DatasetFilter(django_filters.FilterSet):
    # `theme` filters by the top-level theme (via the linked sub_theme's parent) — same
    # convention as apps/publications/views.py's PublicationFilter.
    theme = django_filters.NumberFilter(field_name="sub_theme__parent_id")

    class Meta:
        model = Dataset
        # "theme" isn't a real model field — it's the explicitly declared filter above.
        fields = ["sub_theme", "geography", "year"]


@extend_schema(tags=[MODULE_TAG])
class DatasetViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = DatasetFilter
    search_fields = ["title", "description"]

    def get_queryset(self):
        return visible_datasets_for(self.request.user, super().get_queryset())

    def filter_queryset(self, queryset):
        # DjangoFilterBackend/SearchFilter apply to the list action only — see the matching
        # note in apps/publications/views.py's PublicationViewSet.filter_queryset.
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def get_permissions(self):
        if self.action == "request_access":
            # Any authenticated user (including the "public"/Donor-Visitor role) may request
            # access to a gated dataset — PRD C story 8 — not gated to contributor roles like
            # the viewset's default CanSubmitDraft (which is for create/edit-draft actions).
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=["get"], url_path="preview/table")
    def preview_table(self, request, slug=None):
        dataset = self.get_object()
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            page = 1
        page_size = 50
        try:
            header, rows = table_page(dataset, page, page_size)
        except UnsupportedFormat:
            return Response(
                {"detail": f"Table preview isn't available for format '{dataset.format}'."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except PreviewError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response({"page": page, "page_size": page_size, "header": header, "rows": rows})

    @action(detail=True, methods=["get"], url_path="preview/map")
    def preview_map(self, request, slug=None):
        # Flagged, not silently resolved: the committed Dataset.format choices
        # (csv/parquet/zip) have no spatial format, so there's no source of map-ready
        # geo data yet. See docs/api/module-c-data-repository.md's preview_map note.
        return Response(
            {
                "detail": (
                    "Map preview is not implemented: no spatial format exists in the "
                    "current Dataset schema (formats are csv/parquet/zip). Needs a real "
                    "decision (e.g. a geojson format or a separate geo-reference field) "
                    "before this can be built."
                )
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    @action(detail=True, methods=["get"])
    def download(self, request, slug=None):
        dataset = self.get_object()
        if not can_download(request.user, dataset):
            return Response({"detail": "You do not have access to download this dataset."}, status=403)
        return Response({"file": request.build_absolute_uri(dataset.file.url)})

    @action(detail=True, methods=["post"], url_path="request-access")
    def request_access(self, request, slug=None):
        dataset = self.get_object()
        access_request, created = AccessRequest.objects.get_or_create(user=request.user, dataset=dataset)
        serializer = AccessRequestSerializer(access_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@extend_schema(tags=[MODULE_TAG])
class DashboardViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Dashboard.objects.all()
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated, CanSubmitDraft]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["theme", "geography", "year", "type"]


@extend_schema(tags=[MODULE_TAG])
class AccessRequestQueueView(ListAPIView):
    """GET /access-requests/?status=&dataset= — addition beyond docs/api/module-c-data-repository.md's
    literal endpoint table: staff need to see which {id}s are pending before the PATCH
    review endpoint below is usable. See the plan's "Two additions beyond the docs" note.
    """

    serializer_class = AccessRequestSerializer
    permission_classes = [IsAuthenticated, IsStaffRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "dataset"]
    queryset = AccessRequest.objects.all()


class AccessRequestReviewView(APIView):
    """PATCH /access-requests/{id}/ — proposed shape from docs/api/module-c-data-repository.md,
    mirroring the existing single-field-status-update + AuditLog pattern
    (apps/accounts/views.py's UserRoleUpdateView).
    """

    permission_classes = [IsAuthenticated, IsStaffRole]

    @extend_schema(tags=[MODULE_TAG], request=AccessRequestReviewSerializer, responses=AccessRequestSerializer)
    def patch(self, request, pk):
        try:
            access_request = AccessRequest.objects.get(pk=pk)
        except AccessRequest.DoesNotExist:
            return Response({"detail": "Access request not found."}, status=404)

        new_status = request.data.get("status")
        if new_status not in ("approved", "denied"):
            return Response({"detail": "status must be 'approved' or 'denied'."}, status=400)

        old_status = access_request.status
        access_request.status = new_status
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        AuditLog.objects.create(
            actor=request.user,
            module="datarepo",
            action="access_request_review",
            target=f"accessrequest:{access_request.pk}",
            metadata={"old_status": old_status, "new_status": new_status},
        )

        return Response(AccessRequestSerializer(access_request).data)
