from rest_framework import serializers

from apps.workflow.uploads import DOCUMENT_VALIDATORS, PdfUploadField

from .models import Application, JobOpening

WORKFLOW_FIELDS = ["status", "created_by", "reviewed_by", "created_at", "updated_at", "published_at"]


class JobOpeningSerializer(serializers.ModelSerializer):
    description_pdf = PdfUploadField(
        help_text="The job description as a PDF (up to 5 MB), shown on the opening's page. Send null to remove it."
    )
    is_closed = serializers.BooleanField(read_only=True, help_text="Whether the deadline has passed (India date).")

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
            "writing_sample",
            "description_pdf",
            "is_closed",
            *WORKFLOW_FIELDS,
        ]
        read_only_fields = WORKFLOW_FIELDS

    def validate(self, attrs):
        instance = self.instance
        deadline = attrs["deadline"] if "deadline" in attrs else getattr(instance, "deadline", None)
        rolling = attrs["rolling"] if "rolling" in attrs else getattr(instance, "rolling", False)
        if deadline and "deadline" in attrs:
            # A deadline is what staff mean when they set one: it turns rolling applications off.
            attrs["rolling"] = rolling = False
        if not rolling and not deadline:
            raise serializers.ValidationError({"deadline": "Set a deadline, or choose rolling applications."})
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ApplicationSubmissionSerializer(serializers.ModelSerializer):
    """What an applicant sends. `website` is a honeypot: the form hides it, so only bots fill it in."""

    job = serializers.SlugRelatedField(
        slug_field="slug", queryset=JobOpening.objects.none(), required=False, allow_null=True
    )
    cv = serializers.FileField(validators=DOCUMENT_VALIDATORS)
    cover_letter = serializers.FileField(validators=DOCUMENT_VALIDATORS)
    writing_sample = serializers.FileField(validators=DOCUMENT_VALIDATORS, required=False)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=200)

    class Meta:
        model = Application
        fields = ["kind", "job", "full_name", "email", "cv", "cover_letter", "writing_sample", "website"]

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
        job = attrs.get("job")
        if job and job.is_closed:
            raise serializers.ValidationError(
                {"job": f"Applications for this role closed on {job.deadline:%d %b %Y}.".replace(" 0", " ")}
            )
        if job and job.writing_sample == JobOpening.WritingSample.REQUIRED and not attrs.get("writing_sample"):
            raise serializers.ValidationError({"writing_sample": "This role asks for a writing sample."})
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    """An application as staff see it. Only `status` can be changed; the files are fetched through `files/`."""

    job_title = serializers.CharField(source="job.title", read_only=True, default=None)
    job_slug = serializers.CharField(source="job.slug", read_only=True, default=None)
    has_writing_sample = serializers.SerializerMethodField(help_text="Whether the applicant sent a writing sample.")

    class Meta:
        model = Application
        fields = [
            "id",
            "kind",
            "job_slug",
            "job_title",
            "full_name",
            "email",
            "has_writing_sample",
            "status",
            "created_at",
            "handled_at",
            "handled_by",
        ]
        read_only_fields = [f for f in fields if f != "status"]

    def get_has_writing_sample(self, instance) -> bool:
        return bool(instance.writing_sample)
