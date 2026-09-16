from django.db import models

from apps.workflow.models import WorkflowMixin


class Publication(WorkflowMixin):
    FORMAT_CHOICES = [
        ("report", "Report"),
        ("working_paper", "Working Paper"),
        ("data_story", "Data Story"),
    ]
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("ml", "Malayalam"),
    ]
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    abstract = models.TextField()
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    theme = models.CharField(max_length=100)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
    date = models.DateField()
    authors = models.ManyToManyField("content.PersonProfile", related_name="publications", blank=True)
    views = models.PositiveIntegerField(default=0)
    cover_url = models.URLField(blank=True)

    def __str__(self):
        return self.title
