from rest_framework import serializers

from apps.workflow.uploads import ImageUploadField

from .models import Event

WORKFLOW_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]


class EventSerializer(serializers.ModelSerializer):
    image = ImageUploadField()

    class Meta:
        model = Event
        fields = [
            "id",
            "slug",
            "kind",
            "title",
            "summary",
            "body",
            "start_date",
            "end_date",
            "location",
            "image_url",
            "image",
            "registration_url",
            *WORKFLOW_FIELDS,
        ]
        read_only_fields = WORKFLOW_FIELDS

    def validate_registration_url(self, value):
        # The public page links straight to it.
        if value and not value.lower().startswith("https://"):
            raise serializers.ValidationError("Enter an https:// address.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "The end date can't be before the start date."})
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
