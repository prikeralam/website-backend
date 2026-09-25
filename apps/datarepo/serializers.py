from rest_framework import serializers

from .models import AccessRequest, Dashboard, Dataset
from .permissions import can_download

WORKFLOW_READ_ONLY_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "file",
            "format",
            "sub_theme",
            "geography",
            "year",
            "source",
            "update_frequency",
            "visibility",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The file URL is the download itself; an on_request dataset's must not leak through
        # list/detail responses to anyone the /download/ endpoint would refuse.
        request = self.context.get("request")
        if request is not None and not can_download(request.user, instance):
            data.pop("file", None)
        return data

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
