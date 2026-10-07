from rest_framework import serializers

from apps.publications.models import Publication

from .models import AccessRequest, Collection, Dashboard, Dataset, DatasetFile
from .permissions import can_download, visible_datasets_for

WORKFLOW_READ_ONLY_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]


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
    files = serializers.SerializerMethodField(
        help_text="Every downloadable file: the main one first, then other formats of the same data. "
        "Omitted, like `file`, for callers who may not download the dataset."
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
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = [*WORKFLOW_READ_ONLY_FIELDS, "row_count", "column_count", "columns", "file_size"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The file URL is the download itself; an on_request dataset's must not leak through
        # list/detail responses to anyone the /download/ endpoint would refuse.
        request = self.context.get("request")
        if request is not None and not can_download(request.user, instance):
            data.pop("file", None)
            data.pop("files", None)
        return data

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
