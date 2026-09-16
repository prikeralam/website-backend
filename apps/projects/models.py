from django.db import models

from apps.workflow.models import WorkflowMixin


class Project(WorkflowMixin):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    blurb = models.TextField()
    image_url = models.URLField(blank=True)
    cta_label = models.CharField(max_length=100, blank=True)
    cta_href = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return self.title
