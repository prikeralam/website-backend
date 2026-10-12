from rest_framework import serializers

from apps.workflow.uploads import IMAGE_VALIDATORS, ImageUploadField

from .models import Event, EventImage

WORKFLOW_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]
MAX_LIST_ITEMS = 30


class EventImageSerializer(serializers.ModelSerializer):
    """A gallery photo. Written as multipart (`image`, optional `caption`); reads as its URL (presigned on S3)."""

    image = serializers.FileField(validators=IMAGE_VALIDATORS)

    class Meta:
        model = EventImage
        fields = ["id", "image", "caption"]


class EventSerializer(serializers.ModelSerializer):
    image = ImageUploadField()
    images = EventImageSerializer(many=True, read_only=True)

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
            "mode",
            "start_time",
            "end_time",
            "date_note",
            "collaborators",
            "speakers",
            "focus_areas",
            "image_url",
            "image",
            "images",
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
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        one_day = not end or end == start
        if one_day and start_time and end_time and end_time < start_time:
            raise serializers.ValidationError({"end_time": "The end time can't be before the start time."})
        return attrs

    def _clean_list(self, items):
        items = [item.strip() for item in items]
        if any(not item for item in items):
            raise serializers.ValidationError("Leave out empty lines.")
        if len(items) > MAX_LIST_ITEMS:
            raise serializers.ValidationError(f"Keep this to {MAX_LIST_ITEMS} lines or fewer.")
        return items

    def validate_collaborators(self, value):
        return self._clean_list(value)

    def validate_speakers(self, value):
        return self._clean_list(value)

    def validate_focus_areas(self, value):
        return self._clean_list(value)

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
