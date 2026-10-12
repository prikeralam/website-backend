from rest_framework import serializers

from apps.workflow.uploads import ImageUploadField

from .models import Project

MAX_FACTS = 12
MAX_DETAILS_LENGTH = 40_000


class ProjectSerializer(serializers.ModelSerializer):
    image = ImageUploadField()

    class Meta:
        model = Project
        fields = [
            "id",
            "slug",
            "title",
            "blurb",
            "image_url",
            "image",
            "cta_label",
            "cta_href",
            "stage",
            "facts",
            "details",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "created_by", "reviewed_by", "created_at", "updated_at"]

    def validate_facts(self, value):
        facts = [fact.strip() for fact in value]
        if any(not fact for fact in facts):
            raise serializers.ValidationError("Leave out empty lines.")
        if len(facts) > MAX_FACTS:
            raise serializers.ValidationError(f"Keep this to {MAX_FACTS} lines or fewer.")
        return facts

    def validate_details(self, value):
        if len(value) > MAX_DETAILS_LENGTH:
            raise serializers.ValidationError(f"Keep this under {MAX_DETAILS_LENGTH:,} characters.")
        return value.strip()

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
