import re

import django_filters
from django.db import transaction
from django.db.models import CharField, F, Func, Q, Value
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import AuditLog
from apps.workflow.models import WorkflowStatus
from apps.workflow.permissions import CONTRIBUTOR_ROLES, STAFF_ROLES, CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from . import releases
from .geo import GeoJSONError, GeoJSONTooLarge, load_geojson
from .models import (
    OPEN_RELEASE_STATUSES,
    AccessRequest,
    Collection,
    Dashboard,
    Dataset,
    DatasetDownload,
    DatasetFile,
    DatasetRelease,
    DatasetReleaseFile,
    ReleaseStatus,
)
from .permissions import can_download, can_edit_dataset, visible_datasets_for
from .previews import PreviewError, UnsupportedFormat, table_page
from .serializers import (
    AccessRequestReviewSerializer,
    AccessRequestSerializer,
    CollectionSerializer,
    DashboardSerializer,
    DatasetFileSerializer,
    DatasetReleaseCreateSerializer,
    DatasetReleaseFileSerializer,
    DatasetReleaseSerializer,
    DatasetSerializer,
    ReleaseChecklistSerializer,
    ReleaseMetadataSerializer,
    ReleaseTransitionSerializer,
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
        status_ok = obj.status == WorkflowStatus.APPROVED or (
            f"it must be approved first (it is {obj.get_status_display().lower()})"
        )
        problems = releases.publishing_problems(
            status_ok=status_ok, value=lambda name: getattr(obj, name), columns=obj.columns,
            column_dictionary=obj.column_dictionary, qa_report=obj.qa_report, qa_checklist=obj.qa_checklist,
        )
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
        if self.action in ("releases", "release_detail"):
            # Anyone who can see the dataset reads its published releases; writes are decided per release below.
            return [IsAuthenticatedOrReadOnly()]
        if self.action in ("release_add_file", "release_transition"):
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

    # ------------------------------------------------------------------ releases (B4, #125)
    def _release(self, request, dataset, release_id):
        release = DatasetRelease.objects.filter(dataset=dataset, pk=release_id).prefetch_related("files").first()
        if release is None or not releases.can_see_release(request.user, release):
            return None
        return release

    def _release_audit(self, request, action_name, release, **metadata):
        AuditLog.objects.create(
            actor=request.user, module="datarepo", action=action_name, target=f"datasetrelease:{release.pk}",
            metadata={"dataset": release.dataset.slug, "version": release.version, **metadata},
        )

    def _uploads(self, request):
        """Release files sent as files[<format>]."""
        uploads = {}
        for key, upload in request.FILES.items():
            match = re.fullmatch(r"files\[(\w+)\]", key)
            if not match or match.group(1) not in dict(Dataset.FORMAT_CHOICES):
                raise ValidationError({"files": f"Unexpected file field {key!r}: use files[<format>]."})
            uploads[match.group(1)] = upload
        return uploads

    @extend_schema(methods=["GET"], responses=DatasetReleaseSerializer(many=True))
    @extend_schema(methods=["POST"], request={"multipart/form-data": DatasetReleaseCreateSerializer},
                   responses={201: DatasetReleaseSerializer})
    @action(detail=True, methods=["get", "post"], url_path="releases")
    def releases(self, request, slug=None):
        """GET: the version history (published releases, newest first; staff and the creator also see the others).
        POST: a new version of a published dataset, as multipart `version`, `changelog`, `format` (main file),
        `metadata` (JSON) and `files[<format>]`; the main format's file is required."""
        dataset = self.get_object()
        if request.method == "GET":
            visible = [r for r in dataset.releases.prefetch_related("files")
                       if releases.can_see_release(request.user, r)]
            return Response(DatasetReleaseSerializer(visible, many=True, context={"request": request}).data)

        if not releases.can_release(request.user, dataset):
            self.permission_denied(request, message="You can't post releases of this dataset.")
        if dataset.status != WorkflowStatus.PUBLISHED:
            return Response({"detail": "Releases refresh published datasets; edit this one directly."}, status=400)
        open_release = dataset.releases.filter(status__in=OPEN_RELEASE_STATUSES).first()
        if open_release:
            state = open_release.get_status_display().lower()
            return Response({"detail": f"Release {open_release.version} is still {state}; publish, reject or delete "
                             "it first."}, status=400)
        form = DatasetReleaseCreateSerializer(data=request.data, context={"dataset": dataset})
        form.is_valid(raise_exception=True)
        metadata = form.validated_data.get("metadata") or {}
        meta = ReleaseMetadataSerializer(dataset, data=metadata, partial=True, context={"request": request})
        if not meta.is_valid():
            raise ValidationError({"metadata": meta.errors})
        uploads = self._uploads(request)
        main_format = form.validated_data["format"]
        if main_format not in uploads:
            raise ValidationError({"files": f"Send the main file as files[{main_format}]."})
        stored = []
        try:
            with transaction.atomic():
                releases.ensure_baseline(dataset)
                release = DatasetRelease.objects.create(
                    dataset=dataset, version=form.validated_data["version"],
                    changelog=form.validated_data["changelog"], format=main_format, metadata=metadata,
                    created_by=request.user,
                )
                for fmt, upload in uploads.items():
                    sha256 = releases.sha256_of(upload)
                    saved = DatasetReleaseFile.objects.create(release=release, format=fmt, file=upload,
                                                              size=upload.size, sha256=sha256)
                    stored.append(saved.file)
                # The dictionary must name columns of the new file, which is profiled once stored.
                releases.profile_release(release)
                named = [e.get("name") for e in metadata.get("column_dictionary") or [] if isinstance(e, dict)]
                missing = [name for name in named if release.columns and name not in release.columns]
                if missing:
                    problem = f"Not columns of the file: {', '.join(missing)}."
                    raise ValidationError({"metadata": {"column_dictionary": problem}})
                self._release_audit(request, "release_created", release)
        except ValidationError:
            for f in stored:  # the rows were rolled back; the stored files go too
                f.storage.delete(f.name)
            raise
        return Response(DatasetReleaseSerializer(release, context={"request": request}).data, status=201)

    @extend_schema(methods=["GET"], responses=DatasetReleaseSerializer)
    @extend_schema(methods=["PATCH"], request=ReleaseChecklistSerializer, responses=DatasetReleaseSerializer)
    @extend_schema(methods=["DELETE"], request=None, responses={204: None})
    @action(detail=True, methods=["get", "patch", "delete"], url_path=r"releases/(?P<release_id>\d+)")
    def release_detail(self, request, slug=None, release_id=None):
        """GET one release. PATCH: editors tick its QA checklist. DELETE: its creator while it is a draft, editors and
        admins until it is published (the pipeline replaces a draft by deleting it and posting again)."""
        dataset = self.get_object()
        release = self._release(request, dataset, release_id)
        if release is None:
            return Response({"detail": "No such release of this dataset."}, status=404)
        if request.method == "GET":
            return Response(DatasetReleaseSerializer(release, context={"request": request}).data)
        staff = request.user.role in STAFF_ROLES
        if request.method == "PATCH":
            if not staff:
                self.permission_denied(request, message="Only editors and admins complete the QA checklist.")
            if release.status not in OPEN_RELEASE_STATUSES:
                return Response({"detail": f"This release is {release.status}; its checklist is closed."}, status=400)
            form = ReleaseChecklistSerializer(data=request.data, context={"request": request})
            form.is_valid(raise_exception=True)
            release.qa_checklist = form.validated_data["qa_checklist"]
            release.save(update_fields=["qa_checklist", "updated_at"])
            return Response(DatasetReleaseSerializer(release, context={"request": request}).data)
        own_draft = release.status == ReleaseStatus.DRAFT and release.created_by_id == request.user.id
        if not (own_draft or (staff and release.status != ReleaseStatus.PUBLISHED)):
            self.permission_denied(request, message="You can't delete this release.")
        self._release_audit(request, "release_deleted", release, status=release.status)
        release.delete()  # stored files go too, unless the dataset or another release still uses them
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request={"multipart/form-data": DatasetReleaseFileSerializer},
                   responses={201: DatasetReleaseFileSerializer})
    @action(detail=True, methods=["post"], url_path=r"releases/(?P<release_id>\d+)/files")
    def release_add_file(self, request, slug=None, release_id=None):
        """Add another format to a draft release (one request per file keeps each upload under the 50 MB limit)."""
        dataset = self.get_object()
        release = self._release(request, dataset, release_id)
        if release is None:
            return Response({"detail": "No such release of this dataset."}, status=404)
        own = release.created_by_id == request.user.id or request.user.role in STAFF_ROLES
        if not own or release.status != ReleaseStatus.DRAFT:
            self.permission_denied(request, message="Files can be added to a draft release by its creator or staff.")
        form = DatasetReleaseFileSerializer(data=request.data, context={"release": release})
        form.is_valid(raise_exception=True)
        added = form.save(release=release)
        self._release_audit(request, "release_file_added", release, format=added.format)
        return Response(DatasetReleaseFileSerializer(added).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReleaseTransitionSerializer, responses=DatasetReleaseSerializer)
    @action(detail=True, methods=["post"], url_path=r"releases/(?P<release_id>\d+)/transition")
    def release_transition(self, request, slug=None, release_id=None):
        """Move a release through review: draft -> in_review (its creator or staff), then approved, published,
        rejected or back to draft (editors and admins), with the dataset's gate and two-person rule."""
        dataset = self.get_object()
        release = self._release(request, dataset, release_id)
        if release is None:
            return Response({"detail": "No such release of this dataset."}, status=404)
        form = ReleaseTransitionSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        target = form.validated_data["status"]
        submit = release.status == ReleaseStatus.DRAFT and target == ReleaseStatus.IN_REVIEW
        allowed = request.user.role in STAFF_ROLES or (
            submit and release.created_by_id == request.user.id and request.user.role in CONTRIBUTOR_ROLES
        )
        if not allowed:
            self.permission_denied(request, message="Only editors and admins review releases.")
        blocker = releases.release_transition_blocker(release, target, request.user)
        if blocker:
            return Response({"detail": blocker}, status=400)
        previous = release.status
        if target == ReleaseStatus.PUBLISHED:
            meta = ReleaseMetadataSerializer(dataset, data=release.metadata, partial=True, context={"request": request})
            if not meta.is_valid():
                return Response({"detail": "The release's metadata no longer fits the dataset.",
                                 "metadata": meta.errors}, status=400)
            releases.publish(release, meta)
        else:
            release.status = target
            if target == ReleaseStatus.APPROVED:
                release.approved_by, release.approved_at = request.user, timezone.now()
            elif target in (ReleaseStatus.DRAFT, ReleaseStatus.IN_REVIEW):
                release.approved_by, release.approved_at = None, None
            release.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        self._release_audit(request, "release_transition", release, previous_status=previous, new_status=target)
        return Response(DatasetReleaseSerializer(release, context={"request": request}).data)

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
