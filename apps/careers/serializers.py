from rest_framework import serializers

from apps.workflow.uploads import DOCUMENT_VALIDATORS

from .models import Application, JobOpening

WORKFLOW_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]


class JobOpeningSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOpening
        fields = [
            "id",
            "slug",
            "title",
            "summary",
            "description",
            "location",
            "employment_type",
            "rolling",
            "deadline",
            "display_order",
            *WORKFLOW_FIELDS,
        ]
        read_only_fields = WORKFLOW_FIELDS

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ApplicationSubmissionSerializer(serializers.ModelSerializer):
    """What an applicant sends. `website` is a honeypot: the form hides it, so only bots fill it in."""

    job = serializers.SlugRelatedField(
        slug_field="slug", queryset=JobOpening.objects.none(), required=False, allow_null=True
    )
    cv = serializers.FileField(validators=DOCUMENT_VALIDATORS)
    sop = serializers.FileField(validators=DOCUMENT_VALIDATORS)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=200)

    class Meta:
        model = Application
        fields = ["kind", "job", "full_name", "email", "cv", "sop", "website"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only openings the public can see can be applied for.
        self.fields["job"].queryset = JobOpening.objects.filter(status="published")

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Please enter your full name.")
        return value

    def validate(self, attrs):
        if attrs["kind"] == Application.Kind.JOB and not attrs.get("job"):
            raise serializers.ValidationError({"job": "Choose the role you are applying for."})
        if attrs["kind"] != Application.Kind.JOB:
            attrs["job"] = None
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    """An application as staff see it. Only `status` can be changed; the files are fetched through `files/`."""

    job_title = serializers.CharField(source="job.title", read_only=True, default=None)
    job_slug = serializers.CharField(source="job.slug", read_only=True, default=None)

    class Meta:
        model = Application
        fields = [
            "id",
            "kind",
            "job_slug",
            "job_title",
            "full_name",
            "email",
            "status",
            "created_at",
            "handled_at",
            "handled_by",
        ]
        read_only_fields = [f for f in fields if f != "status"]
