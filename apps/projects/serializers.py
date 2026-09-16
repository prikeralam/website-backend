from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "slug",
            "title",
            "blurb",
            "image_url",
            "cta_label",
            "cta_href",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "created_by", "reviewed_by", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
