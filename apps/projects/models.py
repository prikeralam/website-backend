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

    def __str__(self):
        return self.title
