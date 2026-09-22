from django.conf import settings
from django.db import models

from apps.workflow.models import WorkflowMixin


class Dataset(WorkflowMixin):
    FORMAT_CHOICES = [
        ("csv", "CSV"),
        ("parquet", "Parquet"),
        ("zip", "ZIP"),
    ]
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("on_request", "On Request"),
        ("internal_only", "Internal Only"),
    ]
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="datasets/")
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    # Must reference a sub-theme, not a top-level theme — same rule and same enforcement
    # point (DatasetSerializer.validate_sub_theme) as Publication.sub_theme. Dashboard.theme
    # below is deliberately NOT changed to this rule — only Dataset/Publication were asked for.
    sub_theme = models.ForeignKey("taxonomy.Theme", on_delete=models.PROTECT, related_name="datasets")
    geography = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=200, blank=True)
    update_frequency = models.CharField(max_length=50, blank=True)
    visibility = models.CharField(max_length=15, choices=VISIBILITY_CHOICES, default="internal_only")

    def __str__(self):
        return self.title


class Dashboard(WorkflowMixin):
    EMBED_TYPE_CHOICES = [
        ("datawrapper", "Datawrapper"),
        ("tableau", "Tableau"),
        ("d3", "D3.js"),
    ]
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    embed_url = models.URLField(max_length=500)
    embed_type = models.CharField(max_length=20, choices=EMBED_TYPE_CHOICES)
    theme = models.ForeignKey("taxonomy.Theme", on_delete=models.PROTECT, related_name="dashboards")
    geography = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(null=True, blank=True)
    type = models.CharField(max_length=50, blank=True)
    datasets = models.ManyToManyField(Dataset, related_name="dashboards", blank=True)

    def __str__(self):
        return self.title


class AccessRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_requests")
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="access_requests")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        unique_together = ("user", "dataset")

    def __str__(self):
        return f"{self.user} -> {self.dataset} ({self.status})"
