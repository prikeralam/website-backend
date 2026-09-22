from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.workflow.models import WorkflowMixin


class Publication(WorkflowMixin):
    FORMAT_CHOICES = [
        ("report", "Report"),
        ("working_paper", "Working Paper"),
        ("brief", "Brief"),
        ("explainer", "Explainer"),
        ("infographic", "Infographic"),
        ("video", "Video"),
        ("data_story", "Data Story"),
    ]
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("ml", "Malayalam"),
    ]
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
    ]
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    abstract = models.TextField()
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    # Must reference a sub-theme (a Theme with its own parent set), not a top-level theme —
    # enforced in PublicationSerializer.validate_sub_theme, since Theme itself has no DB-level
    # way to distinguish "top-level" from "sub" beyond parent being null/non-null.
    sub_theme = models.ForeignKey("taxonomy.Theme", on_delete=models.PROTECT, related_name="publications")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
    date = models.DateField()
    authors = models.ManyToManyField("content.PersonProfile", related_name="publications", blank=True)
    external_id = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="public")
    tags = ArrayField(models.CharField(max_length=50), blank=True, default=list)
    views = models.PositiveIntegerField(default=0)
    cover_url = models.URLField(blank=True)

    def __str__(self):
        return self.title


class PublicationVersion(models.Model):
    publication = models.ForeignKey(Publication, related_name="versions", on_delete=models.CASCADE)
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to="publications/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("publication", "version_number")
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.publication.slug} v{self.version_number}"
