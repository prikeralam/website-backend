from django.core.validators import URLValidator
from django.db import models

from apps.workflow.models import WorkflowMixin
from apps.workflow.uploads import IMAGE_VALIDATORS

# Public pages link straight to these, so only https addresses are accepted.
HTTPS_ONLY = URLValidator(schemes=["https"])


class Mention(WorkflowMixin):
    """Somewhere PRI's research or data was cited or covered: news, papers, reports, the legislature."""

    KIND_CHOICES = [
        ("news", "News"),
        ("research", "Research paper"),
        ("report", "Report"),
        ("legislature", "Legislature"),
        ("other", "Other"),
    ]
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=300)
    publisher = models.CharField(max_length=200)
    url = models.URLField(max_length=500, validators=[HTTPS_ONLY])
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="news")
    date = models.DateField()
    summary = models.TextField(blank=True)
    publisher_logo = models.FileField(upload_to="mentions/", blank=True, validators=IMAGE_VALIDATORS)
    # The PRI work that was cited, when there is one.
    publication = models.ForeignKey(
        "publications.Publication", null=True, blank=True, on_delete=models.SET_NULL, related_name="mentions"
    )
    dataset = models.ForeignKey(
        "datarepo.Dataset", null=True, blank=True, on_delete=models.SET_NULL, related_name="mentions"
    )

    class Meta(WorkflowMixin.Meta):
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.publisher}: {self.title}"


class Recognition(WorkflowMixin):
    """An award, grant or membership PRI has received."""

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    awarded_by = models.CharField(max_length=200)
    year = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    url = models.URLField(max_length=500, blank=True, validators=[HTTPS_ONLY])
    image = models.FileField(upload_to="recognition/", blank=True, validators=IMAGE_VALIDATORS)

    class Meta(WorkflowMixin.Meta):
        ordering = ["-year", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.year})"
