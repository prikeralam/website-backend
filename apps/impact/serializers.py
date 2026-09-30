from rest_framework import serializers

from apps.datarepo.models import Dataset
from apps.publications.models import Publication
from apps.workflow.uploads import ImageUploadField

from .models import Mention, Recognition

WORKFLOW_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]


def https_only(value):
    """Public pages link straight to these addresses, so they must be https."""
    if value and not value.lower().startswith("https://"):
        raise serializers.ValidationError("Enter an https:// address.")
    return value


class MentionSerializer(serializers.ModelSerializer):
    publisher_logo = ImageUploadField()
    # The cited PRI work, read and written by slug.
    publication = serializers.SlugRelatedField(
        slug_field="slug", queryset=Publication.objects.all(), required=False, allow_null=True
    )
    dataset = serializers.SlugRelatedField(
        slug_field="slug", queryset=Dataset.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Mention
        fields = [
            "id",
            "slug",
            "title",
            "publisher",
            "url",
            "kind",
            "date",
            "summary",
            "publisher_logo",
            "publication",
            "dataset",
            *WORKFLOW_FIELDS,
        ]
        read_only_fields = WORKFLOW_FIELDS

    def validate_url(self, value):
        return https_only(value)

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class RecognitionSerializer(serializers.ModelSerializer):
    image = ImageUploadField()

    class Meta:
        model = Recognition
        fields = ["id", "slug", "title", "awarded_by", "year", "description", "url", "image", *WORKFLOW_FIELDS]
        read_only_fields = WORKFLOW_FIELDS

    def validate_url(self, value):
        return https_only(value)

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
