import uuid

from django.conf import settings
from django.db import models

from apps.workflow.models import WorkflowMixin
from apps.workflow.uploads import DOCUMENT_VALIDATORS


class JobOpening(WorkflowMixin):
    """A role PRI is hiring for, listed on the careers page."""

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    employment_type = models.CharField(max_length=100, blank=True)
    # Rolling openings take applications at any time; the deadline only applies when this is off.
    rolling = models.BooleanField(default=True)
    deadline = models.DateField(null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta(WorkflowMixin.Meta):
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.title


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
    sop = models.FileField(upload_to=application_upload_to, validators=DOCUMENT_VALIDATORS)
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
