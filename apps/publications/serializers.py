from rest_framework import serializers

from apps.workflow.uploads import ImageUploadField

from .models import Publication, PublicationVersion


class PublicationSerializer(serializers.ModelSerializer):
    cover = ImageUploadField()

    class Meta:
        model = Publication
        fields = [
            "id",
            "slug",
            "title",
            "abstract",
            "format",
            "sub_theme",
            "language",
            "date",
            "authors",
            "external_id",
            "visibility",
            "tags",
            "views",
            "cover_url",
            "cover",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]

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


class PublicationVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationVersion
        fields = ["id", "publication", "version_number", "file", "uploaded_by", "is_current", "created_at"]
        read_only_fields = ["publication", "uploaded_by", "is_current", "created_at"]
