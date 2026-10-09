from rest_framework import serializers

from apps.workflow.models import WorkflowStatus
from apps.workflow.uploads import ImageUploadField, StoryUploadField

from .models import Publication, PublicationVersion


class PublicationSerializer(serializers.ModelSerializer):
    cover = ImageUploadField()
    story_html = StoryUploadField()

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
            "story_html",
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

    def validate(self, attrs):
        # A published publication must keep a cover (see PublicationViewSet.publish_blocker). Only an edit that
        # removes the last one is refused, so older publications without a cover can still be edited.
        instance = self.instance
        had_cover = instance is not None and (instance.cover or instance.cover_url)
        if had_cover and instance.status == WorkflowStatus.PUBLISHED:
            cover = attrs.get("cover", instance.cover)
            cover_url = attrs.get("cover_url", instance.cover_url)
            if not (cover or cover_url):
                raise serializers.ValidationError(
                    {"cover": "A published publication needs a cover image. Add a new one, or unpublish it first."}
                )
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class PublicationVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationVersion
        fields = ["id", "publication", "version_number", "file", "uploaded_by", "is_current", "created_at"]
        read_only_fields = ["publication", "uploaded_by", "is_current", "created_at"]
