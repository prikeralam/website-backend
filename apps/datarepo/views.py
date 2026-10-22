import django_filters
from django.db.models import CharField, F, Func, Q, Value
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import AuditLog
from apps.workflow.models import WorkflowStatus
from apps.workflow.permissions import STAFF_ROLES, CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .geo import GeoJSONError, GeoJSONTooLarge, load_geojson
from .models import (
    PUBLISH_REQUIRED_FIELDS,
    QA_CHECKLIST_ITEMS,
    AccessRequest,
    Collection,
    Dashboard,
    Dataset,
    DatasetDownload,
    DatasetFile,
)
from .permissions import can_download, can_edit_dataset, visible_datasets_for
from .previews import PreviewError, UnsupportedFormat, table_page
from .serializers import (
    AccessRequestReviewSerializer,
    AccessRequestSerializer,
    CollectionSerializer,
    DashboardSerializer,
    DatasetFileSerializer,
    DatasetSerializer,
)

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
        fields = ["sub_theme", "geography", "year", "code", "source_tier", "quality_grade"]


class DatasetSearchFilter(filters.SearchFilter):
    """`?q=` over title, description, summary and keywords (every term must match one of them).

    `keywords` is a Postgres array, which DRF's SearchFilter can't search, so it is searched as joined text."""

    def filter_queryset(self, request, queryset, view):
        terms = self.get_search_terms(request)
        if not terms:
            return queryset
        queryset = queryset.annotate(
            keywords_text=Func(F("keywords"), Value(" "), function="array_to_string", output_field=CharField())
        )
        for term in terms:
            queryset = queryset.filter(
                Q(title__icontains=term) | Q(description__icontains=term) | Q(summary__icontains=term)
                | Q(keywords_text__icontains=term)
            )
        return queryset


@extend_schema(tags=[MODULE_TAG])
class DatasetViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, DatasetSearchFilter]
    filterset_class = DatasetFilter
    search_fields = ["title", "description", "summary", "keywords"]

    def get_queryset(self):
        return visible_datasets_for(self.request.user, super().get_queryset()).prefetch_related(
            "extra_files", "related_publications"
        )

    def publish_blocker(self, obj):
        """The PRI Data Framework's publishing gate: one sentence naming everything still missing."""
        problems = []
        if obj.status != WorkflowStatus.APPROVED:
            problems.append(f"it must be approved first (it is {obj.get_status_display().lower()})")
        empty = [name for name in PUBLISH_REQUIRED_FIELDS if getattr(obj, name) in (None, "")]
        if empty:
            problems.append("these fields are empty: " + ", ".join(empty))
        if obj.source_tier == "4":
            problems.append("tier 4 sources (news, unverified files) are never published")
        labelled = {e.get("name") for e in obj.column_dictionary or [] if str(e.get("label") or "").strip()}
        unlabelled = [c for c in obj.columns or [] if c not in labelled]
        if unlabelled:
            problems.append("these columns have no label in the column dictionary: " + ", ".join(unlabelled))
        if (obj.qa_report or {}).get("passed") is not True:
            problems.append("the automated QA report has not passed (run `pri publish --check`)")
        checklist = obj.qa_checklist or {}
        open_items = [key for key, _ in QA_CHECKLIST_ITEMS if checklist.get(key) is not True]
        if open_items:
            problems.append("the QA checklist is not complete (open: " + ", ".join(open_items) + ")")
        if not problems:
            return None
        return "This dataset can't be published yet: " + "; ".join(problems) + "."

    def transition_blocker(self, obj, target, user):
        # Two-person rule, creator half: whoever created a dataset doesn't approve it. The approver may publish for now
        # (#131, a single editor approves and publishes until a second one joins); the check comes back later.
        if target == WorkflowStatus.APPROVED and obj.created_by_id == user.id:
            return "You created this dataset, so another editor has to approve it."
        return super().transition_blocker(obj, target, user)

    def after_transition(self, obj, previous, target, user):
        if target == WorkflowStatus.APPROVED:
            obj.approved_by, obj.approved_at = user, timezone.now()
        elif target in (WorkflowStatus.DRAFT, WorkflowStatus.IN_REVIEW):
            obj.approved_by, obj.approved_at = None, None
        else:
            return
        obj.save(update_fields=["approved_by", "approved_at"])

    def filter_queryset(self, queryset):
        # DjangoFilterBackend/SearchFilter apply to the list action only — see the matching
        # note in apps/publications/views.py's PublicationViewSet.filter_queryset.
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def get_permissions(self):
        if self.action in ("add_file", "remove_file"):
            # Who may change the files is decided per dataset by can_edit_dataset (see _editable_dataset).
            return [IsAuthenticated()]
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
        dataset = self.get_object()
        if dataset.format != "geojson":
            return Response(
                {"detail": f"Map preview needs a 'geojson' dataset, not '{dataset.format}'."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        try:
            return Response(load_geojson(dataset))
        except GeoJSONTooLarge:
            return Response(
                {"detail": "This GeoJSON file is too large to preview on a map."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        except GeoJSONError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @extend_schema(
        parameters=[OpenApiParameter("format", str, description="A format from `files`; the main file when omitted.")]
    )
    @action(detail=True, methods=["get"])
    def download(self, request, slug=None):
        dataset = self.get_object()
        if not can_download(request.user, dataset):
            return Response({"detail": "You do not have access to download this dataset."}, status=403)
        wanted = request.query_params.get("format")
        if not wanted or wanted == dataset.format:
            url, fmt = dataset.file.url, dataset.format
        else:
            extra = dataset.extra_files.filter(format=wanted).first()
            if extra is None:
                return Response({"detail": f"This dataset has no '{wanted}' file."}, status=404)
            url, fmt = extra.file.url, extra.format
        # Every link handed to an account is recorded, so admins can see who uses which data.
        if request.user.is_authenticated:
            DatasetDownload.objects.create(user=request.user, dataset=dataset, format=fmt)
        return Response({"file": request.build_absolute_uri(url)})

    def _editable_dataset(self, request):
        dataset = self.get_object()
        if not can_edit_dataset(request.user, dataset):
            self.permission_denied(request, message="You can't change this dataset's files.")
        return dataset

    @extend_schema(request={"multipart/form-data": DatasetFileSerializer}, responses={201: DatasetFileSerializer})
    @action(detail=True, methods=["post"], url_path="files")
    def add_file(self, request, slug=None):
        """Add the same data in another format. Same permission as editing the dataset."""
        dataset = self._editable_dataset(request)
        serializer = DatasetFileSerializer(data=request.data, context={"dataset": dataset, "request": request})
        serializer.is_valid(raise_exception=True)
        extra = serializer.save(dataset=dataset)
        AuditLog.objects.create(
            actor=request.user,
            module="datarepo",
            action="dataset_file_added",
            target=f"dataset:{dataset.pk}",
            metadata={"format": extra.format, "file_id": extra.pk},
        )
        return Response(DatasetFileSerializer(extra).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"files/(?P<file_id>\d+)")
    def remove_file(self, request, slug=None, file_id=None):
        """Remove one extra format; its stored file is deleted too."""
        dataset = self._editable_dataset(request)
        extra = DatasetFile.objects.filter(dataset=dataset, pk=file_id).first()
        if extra is None:
            return Response({"detail": "No such file on this dataset."}, status=404)
        AuditLog.objects.create(
            actor=request.user,
            module="datarepo",
            action="dataset_file_removed",
            target=f"dataset:{dataset.pk}",
            metadata={"format": extra.format, "file_id": extra.pk},
        )
        extra.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["theme", "geography", "year", "type"]


@extend_schema(tags=[MODULE_TAG])
class CollectionViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = Collection.objects.prefetch_related("datasets").select_related("publication")
    serializer_class = CollectionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"


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
