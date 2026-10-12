from urllib.parse import urlparse

from rest_framework import serializers

from apps.workflow.uploads import ImageUploadField

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
    photo = ImageUploadField()

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
            "photo",
            "linkedin_url",
            "email",
            "website_url",
            "display_order",
            "status",
            "created_by",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = WORKFLOW_READ_ONLY_FIELDS

    def validate_linkedin_url(self, value):
        # Shown as a link on the public site, so it may only point at LinkedIn itself.
        if not value:
            return value
        parts = urlparse(value)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
            raise serializers.ValidationError("Enter an https:// link to a linkedin.com profile.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        group = attrs.get("group", getattr(self.instance, "group", None))
        role = attrs.get("role_title", getattr(self.instance, "role_title", ""))
        if group != "advisory" and not (role or "").strip():
            raise serializers.ValidationError(
                {"role_title": "Add a role. Only Advisory Body members can be left without one."}
            )
        return attrs

    def validate_website_url(self, value):
        # Partners' cards link straight to it.
        if value and urlparse(value).scheme != "https":
            raise serializers.ValidationError("Enter an https:// address.")
        return value

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
