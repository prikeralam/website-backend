from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.workflow.models import WorkflowMixin
from apps.workflow.uploads import IMAGE_VALIDATORS


class Project(WorkflowMixin):
    class Stage(models.TextChoices):
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    blurb = models.TextField()
    image_url = models.URLField(blank=True)
    # An uploaded image wins over image_url when both are set.
    image = models.FileField(upload_to="projects/", blank=True, validators=IMAGE_VALIDATORS)
    cta_label = models.CharField(max_length=100, blank=True)
    cta_href = models.CharField(max_length=300, blank=True)
    # Where the project itself stands, shown on project cards. Separate from the workflow `status`.
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.ONGOING)
    # The project page's fact sheet, one "Label: value" line each, e.g. "Project duration: 2025 - 2026".
    facts = ArrayField(models.CharField(max_length=500), blank=True, default=list)
    # The long write-up in a small Markdown subset the frontend renders: "## " starts a section, "### " a sub-section,
    # "- " a bullet, **bold** inline. Text before the first section is the overview, shown open.
    details = models.TextField(blank=True)

    def __str__(self):
        return self.title
