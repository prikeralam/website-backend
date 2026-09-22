from rest_framework import serializers

from .models import ContentBlock, Document, PersonProfile, Testimonial

WORKFLOW_READ_ONLY_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at"]


class ContentBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentBlock
        fields = [
            "id",
            "slug",
            "title",
            "body",
            "seo_title",
            "seo_description",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class LatestUpdateItemSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.IntegerField()
    slug = serializers.CharField()
    title = serializers.CharField()
    published_at = serializers.DateTimeField()


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = [
            "id",
            "slug",
            "quote",
            "attribution",
            "role",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class PersonProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonProfile
        fields = [
            "id",
            "slug",
            "name",
            "role_title",
            "group",
            "bio",
            "photo_url",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "slug",
            "title",
            "file",
            "description",
            "document_type",
            "year",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
