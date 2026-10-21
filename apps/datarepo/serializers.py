import re

from rest_framework import serializers

from apps.publications.models import Publication
from apps.workflow.models import WorkflowStatus
from apps.workflow.permissions import STAFF_ROLES

from .models import (
    PUBLISH_REQUIRED_FIELDS,
    QA_CHECKLIST_ITEMS,
    AccessRequest,
    Collection,
    Dashboard,
    Dataset,
    DatasetFile,
)
from .permissions import can_download, visible_datasets_for

WORKFLOW_READ_ONLY_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]
CODE_PATTERN = re.compile(r"^PRI-[A-Z]{3}-\d{4}$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
MAX_LIST_ITEMS = 12
COLUMN_KEYS = {"name", "label", "description", "data_type", "unit", "allowed_values", "null_meaning",
               "source_column", "derived_formula"}


def _clean_list(items):
    items = [item.strip() for item in items]
    if any(not item for item in items):
        raise serializers.ValidationError("Leave out empty entries.")
    if len(items) > MAX_LIST_ITEMS:
        raise serializers.ValidationError(f"Keep this to {MAX_LIST_ITEMS} entries or fewer.")
    return items


def _file_entry(request, *, format, file, size, id=None):
    url = file.url
    return {
        "id": id,
        "format": format,
        "label": dict(Dataset.FORMAT_CHOICES).get(format, format.upper()),
        "url": request.build_absolute_uri(url) if request is not None else url,
        "size": size,
    }


class DatasetFileSerializer(serializers.ModelSerializer):
    """An extra format of a dataset, as uploaded by staff. The dataset comes from the URL."""

    class Meta:
        model = DatasetFile
        fields = ["id", "format", "file", "size", "created_at"]
        read_only_fields = ["id", "size", "created_at"]

    def validate_format(self, value):
        dataset = self.context["dataset"]
        if value == dataset.format:
            raise serializers.ValidationError("That is already the dataset's main file format.")
        if dataset.extra_files.filter(format=value).exists():
            raise serializers.ValidationError("This dataset already has a file in that format; remove it first.")
        return value


class DatasetSerializer(serializers.ModelSerializer):
    formats = serializers.SerializerMethodField(
        help_text="Every format the dataset comes in, main first. Always shown, even when `files` is not."
    )
    files = serializers.SerializerMethodField(
        help_text="Every downloadable file: the main one first, then other formats of the same data. "
        "Omitted, like `file`, for callers who may not download the dataset."
    )
    code = serializers.CharField(
        max_length=20, required=False, allow_null=True, allow_blank=True,
        help_text="Permanent dataset ID, e.g. PRI-EDU-0012 (from pri-data's catalog). Blank means none.",
    )
    related_publications = serializers.SlugRelatedField(
        slug_field="slug", many=True, queryset=Publication.objects.all(), required=False,
        help_text="Publications that use this dataset, by slug.",
    )
    qa_checklist_items = serializers.SerializerMethodField(
        help_text="The manual QA checklist: the keys `qa_checklist` takes, with their labels, in order."
    )

    class Meta:
        model = Dataset
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "file",
            "format",
            "formats",
            "files",
            "sub_theme",
            "geography",
            "year",
            "source",
            "update_frequency",
            "visibility",
            "granularity",
            "time_period",
            "citation",
            "row_count",
            "column_count",
            "columns",
            "file_size",
            "code",
            "version",
            "summary",
            "keywords",
            "source_publisher",
            "source_document",
            "source_url",
            "archived_url",
            "retrieval_date",
            "source_tier",
            "collection_method",
            "source_terms",
            "period_type",
            "next_update",
            "methodology",
            "known_limitations",
            "lgd_levels",
            "quality_grade",
            "license",
            "steward",
            "contact",
            "related_publications",
            "column_dictionary",
            "provenance",
            "qa_report",
            "qa_checklist",
            "qa_checklist_items",
            "approved_by",
            "approved_at",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = [
            *WORKFLOW_READ_ONLY_FIELDS, "row_count", "column_count", "columns", "file_size", "approved_by",
            "approved_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The file URL is the download itself; an on_request dataset's must not leak through
        # list/detail responses to anyone the /download/ endpoint would refuse.
        request = self.context.get("request")
        if request is not None and not can_download(request.user, instance):
            data.pop("file", None)
            data.pop("files", None)
        return data

    def get_formats(self, instance) -> list[str]:
        return [instance.format, *(extra.format for extra in instance.extra_files.all())]

    def get_files(self, instance) -> list[dict]:
        request = self.context.get("request")
        files = []
        if instance.file:
            files.append(_file_entry(request, format=instance.format, file=instance.file, size=instance.file_size))
        for extra in instance.extra_files.all():
            files.append(_file_entry(request, id=extra.id, format=extra.format, file=extra.file, size=extra.size))
        return files

    def validate_sub_theme(self, sub_theme):
        if sub_theme.parent_id is None:
            raise serializers.ValidationError(
                "sub_theme must be an actual sub-theme (its parent must be set) — "
                f"'{sub_theme.name}' is a top-level theme. Create a sub-theme under it first "
                f"via POST /themes/{sub_theme.pk}/subthemes/."
            )
        return sub_theme

    def get_qa_checklist_items(self, instance) -> list[dict]:
        return [{"key": key, "label": label} for key, label in QA_CHECKLIST_ITEMS]

    def validate_code(self, value):
        if not value:
            return None
        if not CODE_PATTERN.match(value):
            raise serializers.ValidationError("Use the catalog ID form PRI-EDU-0012 (theme code + 4 digits).")
        return value

    def validate_version(self, value):
        if value and not VERSION_PATTERN.match(value):
            raise serializers.ValidationError("Use a semantic version such as 1.0.0.")
        return value

    def validate_source_url(self, value):
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("The source URL must start with https://.")
        return value

    def validate_keywords(self, value):
        return _clean_list(value)

    def validate_lgd_levels(self, value):
        return _clean_list(value)

    def validate_column_dictionary(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Send a list with one entry per column.")
        names = []
        for i, entry in enumerate(value):
            if not isinstance(entry, dict):
                raise serializers.ValidationError(f"Entry {i + 1} must be an object.")
            unknown = set(entry) - COLUMN_KEYS
            if unknown:
                raise serializers.ValidationError(f"Entry {i + 1} has unknown keys: {', '.join(sorted(unknown))}.")
            if not str(entry.get("name") or "").strip() or not str(entry.get("label") or "").strip():
                raise serializers.ValidationError(f"Entry {i + 1} needs a name and a label.")
            if any(v is not None and not isinstance(v, str) for v in entry.values()):
                raise serializers.ValidationError(f"Entry {i + 1}: every value must be text.")
            names.append(entry["name"])
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Each column may appear only once.")
        return value

    def validate_qa_checklist(self, value):
        request = self.context.get("request")
        if getattr(getattr(request, "user", None), "role", None) not in STAFF_ROLES:
            raise serializers.ValidationError("Only editors and admins complete the QA checklist.")
        if not isinstance(value, dict):
            raise serializers.ValidationError("Send an object of {item key: true/false}.")
        known = {key for key, _ in QA_CHECKLIST_ITEMS}
        unknown = set(value) - known
        if unknown:
            raise serializers.ValidationError(f"Unknown checklist items: {', '.join(sorted(unknown))}.")
        if any(not isinstance(done, bool) for done in value.values()):
            raise serializers.ValidationError("Each item is true (done) or false.")
        return value

    def validate(self, attrs):
        instance = self.instance
        # Dictionary names must be real columns once the file has been profiled (a new file is profiled on save).
        dictionary = attrs.get("column_dictionary")
        if dictionary and instance is not None and instance.columns and "file" not in attrs:
            missing = [e["name"] for e in dictionary if e["name"] not in instance.columns]
            if missing:
                raise serializers.ValidationError(
                    {"column_dictionary": f"Not columns of the file: {', '.join(missing)}."}
                )
        # A published dataset keeps what the publish gate required. Older ones that never had a field can still be
        # edited; only an edit that empties a field which was filled is refused.
        if instance is not None and instance.status == WorkflowStatus.PUBLISHED:
            emptied = [name for name in PUBLISH_REQUIRED_FIELDS
                       if name in attrs and attrs[name] in (None, "") and getattr(instance, name) not in (None, "")]
            if emptied:
                raise serializers.ValidationError(
                    {name: "A published dataset needs this. Fill it in, or unpublish the dataset first."
                     for name in emptied}
                )
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class DashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dashboard
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "embed_url",
            "embed_type",
            "theme",
            "geography",
            "year",
            "type",
            "datasets",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class AccessRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessRequest
        fields = ["id", "user", "dataset", "status", "requested_at", "reviewed_at", "reviewed_by"]
        read_only_fields = ["user", "status", "requested_at", "reviewed_at", "reviewed_by"]


class AccessRequestReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[("approved", "Approved"), ("denied", "Denied")])


class CollectionSerializer(serializers.ModelSerializer):
    # Datasets and the linked publication are read and written by slug.
    datasets = serializers.SlugRelatedField(
        slug_field="slug", many=True, queryset=Dataset.objects.all(), required=False
    )
    publication = serializers.SlugRelatedField(
        slug_field="slug", queryset=Publication.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Collection
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "datasets",
            "publication",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def to_representation(self, instance):
        # List only the datasets this caller could open: the same workflow and visibility-tier rules as the
        # dataset endpoints, so a collection never reveals a draft or internal dataset, not even its slug.
        from apps.workflow.permissions import visible_workflow_objects

        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        visible = visible_datasets_for(user, visible_workflow_objects(user, instance.datasets.all()))
        data["datasets"] = list(visible.values_list("slug", flat=True))
        return data

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
