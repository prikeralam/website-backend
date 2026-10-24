from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.workflow.models import WorkflowMixin

# The QA analyst's manual checks before a dataset is approved (pri-data docs/PUBLISHING_PLAN.md Appendix D).
QA_CHECKLIST_ITEMS = [
    ("source_opens", "Source opens; archived copy opens; tier is right."),
    ("row_count", "Row count matches the source, or the difference is explained in limitations."),
    ("sample_rows", "At least 20 random rows checked against the original file."),
    ("totals", "Totals reconcile (counts within 1, percentages within 0.1), or the gap is explained."),
    ("geography_codes", "Geography codes look right on a sample (district names and LGD codes match)."),
    ("units_periods", "Units, period type and time period are correct."),
    ("no_personal_data", "No personal data; small counts suppressed where needed."),
    ("dictionary", "Column dictionary is understandable to an outsider."),
    ("text", "Description, methodology and limitations read clearly."),
    ("downloads", "Every download (CSV, XLSX, Parquet) opens; Malayalam text displays correctly."),
    ("grade", "Quality grade confirmed."),
]

# Fields a dataset must have before it can be published (the publish gate), in the order they are reported.
PUBLISH_REQUIRED_FIELDS = [
    "code", "version", "title", "summary", "description", "sub_theme", "source_publisher", "source_url",
    "archived_url", "retrieval_date", "source_tier", "collection_method", "geography", "granularity", "time_period",
    "period_type", "update_frequency", "methodology", "known_limitations", "license", "steward", "quality_grade",
]

# Formats a dataset's files can be in. Previews (previews.py, geo.py) read only some of them; the rest are downloads.
FORMAT_CHOICES = [
    ("csv", "CSV"),
    ("parquet", "Parquet"),
    ("zip", "ZIP"),
    ("geojson", "GeoJSON"),
    ("json", "JSON"),
    ("xlsx", "Excel"),
]


class Dataset(WorkflowMixin):
    FORMAT_CHOICES = FORMAT_CHOICES
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
    granularity = models.CharField(max_length=120, blank=True)
    time_period = models.CharField(max_length=60, blank=True)
    # Custom citation text; clients build a default one when it's blank.
    citation = models.TextField(blank=True)
    # Worked out from the file whenever it changes (see save()); empty when the file can't be read.
    row_count = models.PositiveIntegerField(null=True, blank=True)
    column_count = models.PositiveIntegerField(null=True, blank=True)
    columns = models.JSONField(default=list, blank=True)
    # Size of the main file in bytes, recorded when the file changes, so listings don't ask storage for it.
    file_size = models.PositiveBigIntegerField(null=True, blank=True)

    # PRI Data Framework metadata (pri-data docs/PUBLISHING_PLAN.md B1). Optional in the database so older rows
    # stay valid; the publish gate (DatasetViewSet.publish_blocker) is what requires them.
    SOURCE_TIER_CHOICES = [("1", "1 Official producer"), ("2", "2 Official, second-hand or RTI"),
                           ("3", "3 Research or civil society"), ("4", "4 Unverified"), ("P", "P PRI")]
    COLLECTION_METHOD_CHOICES = [("administrative", "Administrative"), ("census", "Census"),
                                 ("sample_survey", "Sample survey"), ("rti", "RTI reply"),
                                 ("pri_primary", "PRI primary data"), ("compiled", "Compiled")]
    PERIOD_TYPE_CHOICES = [("calendar_year", "Calendar year"), ("fiscal_year", "Fiscal year"),
                           ("academic_year", "Academic year"), ("survey_year", "Survey year"),
                           ("snapshot", "Snapshot"), ("other", "Other")]
    QUALITY_GRADE_CHOICES = [("A", "A"), ("B", "B"), ("C", "C")]
    LICENSE_CHOICES = [("CC-BY-4.0", "CC BY 4.0"), ("CC-BY-NC-4.0", "CC BY-NC 4.0"), ("GODL-India", "GODL-India"),
                       ("ODbL-1.0", "ODbL 1.0"), ("other", "Other")]

    code = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None)
    version = models.CharField(max_length=20, blank=True)
    summary = models.CharField(max_length=200, blank=True)
    keywords = ArrayField(models.CharField(max_length=60), blank=True, default=list)
    source_publisher = models.CharField(max_length=200, blank=True)
    source_document = models.CharField(max_length=300, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    archived_url = models.URLField(max_length=500, blank=True)
    retrieval_date = models.DateField(null=True, blank=True)
    source_tier = models.CharField(max_length=1, choices=SOURCE_TIER_CHOICES, blank=True)
    collection_method = models.CharField(max_length=30, choices=COLLECTION_METHOD_CHOICES, blank=True)
    source_terms = models.CharField(max_length=300, blank=True)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, blank=True)
    next_update = models.CharField(max_length=60, blank=True)
    methodology = models.TextField(blank=True)
    known_limitations = models.TextField(blank=True)
    lgd_levels = ArrayField(models.CharField(max_length=30), blank=True, default=list)
    quality_grade = models.CharField(max_length=1, choices=QUALITY_GRADE_CHOICES, blank=True)
    license = models.CharField(max_length=40, choices=LICENSE_CHOICES, blank=True, default="CC-BY-4.0")
    steward = models.CharField(max_length=120, blank=True)
    contact = models.EmailField(blank=True)
    related_publications = models.ManyToManyField("publications.Publication", related_name="datasets", blank=True)
    # [{name, label, description, data_type, unit, allowed_values, null_meaning, ...}], one per column.
    column_dictionary = models.JSONField(default=list, blank=True)
    # Where the files came from: {pipeline_repo, git_sha, run_ids, schema_version, built_at, inputs, files}.
    provenance = models.JSONField(default=dict, blank=True)
    # Output of `pri publish --check`: {passed, grade_proposed, checks: [{id, name, status, detail}]}.
    qa_report = models.JSONField(default=dict, blank=True)
    # The QA analyst's manual checklist {item key: done} (QA_CHECKLIST_ITEMS); editor/admin only.
    qa_checklist = models.JSONField(default=dict, blank=True)
    # Set on the move to approved and cleared on a move back (kept for the approver-can't-publish rule, lifted in #131).
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_file_name = instance.file.name if "file" in field_names else None
        return instance

    def refresh_file_stats(self):
        from .previews import profile_file

        profile = profile_file(self)
        self.row_count, self.columns = (profile[0], profile[1]) if profile else (None, [])
        self.column_count = len(self.columns) if profile else None
        try:
            self.file_size = self.file.size
        except (OSError, ValueError):
            self.file_size = None

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file and self.file.name != getattr(self, "_loaded_file_name", None):
            self.refresh_file_stats()
            super().save(update_fields=["row_count", "column_count", "columns", "file_size"])
            self._loaded_file_name = self.file.name

    def __str__(self):
        return self.title


class DatasetFile(models.Model):
    """The same data as a dataset's primary file, in another format, offered as an extra download.

    The primary file (`Dataset.file`) stays the one previews, stats and dashboards read; these only add download
    options and share the dataset's access rules.
    """

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="extra_files")
    file = models.FileField(upload_to="datasets/")
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    size = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["format"]
        constraints = [models.UniqueConstraint(fields=["dataset", "format"], name="one_extra_file_per_format")]

    def save(self, *args, **kwargs):
        if self.file and self.size is None:
            self.size = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dataset.slug} ({self.format})"


class ReleaseStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_REVIEW = "in_review", "In Review"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


# A dataset has at most one release on its way to publication at a time.
OPEN_RELEASE_STATUSES = [ReleaseStatus.DRAFT, ReleaseStatus.IN_REVIEW, ReleaseStatus.APPROVED]


class DatasetRelease(models.Model):
    """A new version of a published dataset (pri-data docs/PUBLISHING_PLAN.md B4).

    It carries its own files and a snapshot of the framework metadata, goes through review like a dataset, and on
    publication replaces the dataset's files and metadata while the dataset stays published. Published releases are the
    version history: their files stay downloadable after a newer release replaces them.
    """

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="releases")
    version = models.CharField(max_length=20)
    changelog = models.TextField(blank=True)
    # The dataset fields this release sets when published (RELEASE_METADATA_FIELDS in releases.py).
    metadata = models.JSONField(default=dict, blank=True)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, help_text="Format of the main file.")
    status = models.CharField(max_length=20, choices=ReleaseStatus.choices, default=ReleaseStatus.DRAFT)
    qa_checklist = models.JSONField(default=dict, blank=True)
    # Profile of the main file, worked out on upload, so the gate can check the column labels before publishing.
    row_count = models.PositiveIntegerField(null=True, blank=True)
    column_count = models.PositiveIntegerField(null=True, blank=True)
    columns = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="+", on_delete=models.PROTECT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        constraints = [
            # A rejected release gives its version back, so the corrected files can be sent under the same number.
            models.UniqueConstraint(
                fields=["dataset", "version"], condition=~models.Q(status="rejected"), name="one_release_per_version"
            ),
            models.UniqueConstraint(
                fields=["dataset"], condition=models.Q(status__in=["draft", "in_review", "approved"]),
                name="one_open_release_per_dataset",
            ),
        ]

    @property
    def main_file(self):
        return next((f for f in self.files.all() if f.format == self.format), None)

    def __str__(self):
        return f"{self.dataset.slug} {self.version} ({self.status})"


class DatasetReleaseFile(models.Model):
    """One format of a release's data. Published releases share their stored files with the dataset."""

    release = models.ForeignKey(DatasetRelease, on_delete=models.CASCADE, related_name="files")
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    file = models.FileField(upload_to="datasets/releases/")
    size = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["format"]
        constraints = [models.UniqueConstraint(fields=["release", "format"], name="one_release_file_per_format")]

    def __str__(self):
        return f"{self.release} ({self.format})"


def stored_file_in_use(name):
    """Whether a dataset, an extra format or a release still points at this stored file (releases share files)."""
    return (
        Dataset.objects.filter(file=name).exists()
        or DatasetFile.objects.filter(file=name).exists()
        or DatasetReleaseFile.objects.filter(file=name).exists()
    )


@receiver(post_delete, sender=DatasetFile)
@receiver(post_delete, sender=DatasetReleaseFile)
def _delete_stored_file(sender, instance, **kwargs):
    # Runs for direct deletes and for cascades from the dataset, so no extra format is left in the bucket. A file that a
    # release (or, for a release file, the dataset) still uses is kept.
    if instance.file and not stored_file_in_use(instance.file.name):
        instance.file.delete(save=False)


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


class DatasetDownload(models.Model):
    """A download link issued to a signed-in user by `/download/`, so admins can see who uses which data.

    It records that a link was handed out, not that the file's bytes were fetched: the file itself is served by storage.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dataset_downloads")
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="downloads")
    format = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["dataset", "created_at"])]

    def __str__(self):
        return f"{self.user} downloaded {self.dataset} ({self.format})"


class Collection(WorkflowMixin):
    """A named bundle of related datasets, for example everything behind one data story."""

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    datasets = models.ManyToManyField(Dataset, related_name="collections", blank=True)
    publication = models.ForeignKey(
        "publications.Publication", null=True, blank=True, on_delete=models.SET_NULL, related_name="collections"
    )

    def __str__(self):
        return self.title
