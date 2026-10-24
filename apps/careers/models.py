import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.workflow.models import WorkflowMixin
from apps.workflow.uploads import DOCUMENT_VALIDATORS, PDF_VALIDATORS

# Deadlines are dates in India, whatever the server's time zone (settings use UTC).
INDIA = ZoneInfo("Asia/Kolkata")


class JobOpening(WorkflowMixin):
    """A role PRI is hiring for, listed on the careers page."""

    class WritingSample(models.TextChoices):
        OPTIONAL = "optional", "Optional"
        REQUIRED = "required", "Required"

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    employment_type = models.CharField(max_length=100, blank=True)
    # Rolling openings take applications at any time and have no deadline; the others close after their deadline.
    rolling = models.BooleanField(default=False)
    deadline = models.DateField(null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    # Whether applicants for this role must send a writing sample (e.g. research roles); optional otherwise.
    writing_sample = models.CharField(max_length=10, choices=WritingSample.choices, default=WritingSample.OPTIONAL)
    # The full job description as a PDF, shown on the opening's page for applicants to download and share.
    description_pdf = models.FileField(upload_to="jobs/", blank=True, validators=PDF_VALIDATORS)

    class Meta(WorkflowMixin.Meta):
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.title

    @property
    def is_closed(self) -> bool:
        """Whether the deadline has passed: applications are taken until the end of the deadline day in India."""
        return self.deadline is not None and self.deadline < timezone.localdate(timezone=INDIA)


def application_upload_to(instance, filename):
    # Random names: applicants' files must not be findable by guessing a URL.
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"applications/{uuid.uuid4().hex}.{extension}"


class Application(models.Model):
    """An application sent through the website: a fellowship, an internship or one of the job openings."""

    class Kind(models.TextChoices):
        FELLOWSHIP = "fellowship", "Fellowship"
        INTERNSHIP = "internship", "Internship"
        JOB = "job", "Job"

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    job = models.ForeignKey(JobOpening, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications")
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    cv = models.FileField(upload_to=application_upload_to, validators=DOCUMENT_VALIDATORS)
    cover_letter = models.FileField(upload_to=application_upload_to, validators=DOCUMENT_VALIDATORS)
    writing_sample = models.FileField(upload_to=application_upload_to, validators=DOCUMENT_VALIDATORS, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} application from {self.full_name}"


# Module-level names for the API schema's enum overrides (settings.SPECTACULAR_SETTINGS).
APPLICATION_KIND_CHOICES = Application.Kind.choices
APPLICATION_STATUS_CHOICES = Application.Status.choices
WRITING_SAMPLE_CHOICES = JobOpening.WritingSample.choices
