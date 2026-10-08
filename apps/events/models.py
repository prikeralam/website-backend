from django.core.validators import URLValidator
from django.db import models

from apps.workflow.models import WorkflowMixin
from apps.workflow.uploads import IMAGE_VALIDATORS


class Event(WorkflowMixin):
    """An event or a campaign on the Events & Campaigns page."""

    class Kind(models.TextChoices):
        EVENT = "event", "Event"
        CAMPAIGN = "campaign", "Campaign"

    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.EVENT)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    body = models.TextField(blank=True)
    start_date = models.DateField()
    # Campaigns and multi-day events run until here; one-day events leave it empty.
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(blank=True)
    # An uploaded image wins over image_url when both are set.
    image = models.FileField(upload_to="events/", blank=True, validators=IMAGE_VALIDATORS)
    # Visitors register elsewhere (a form or ticketing page); the site links straight to it.
    registration_url = models.URLField(max_length=500, blank=True, validators=[URLValidator(schemes=["https"])])

    class Meta(WorkflowMixin.Meta):
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return self.title


# Module-level name for the API schema's enum overrides (settings.SPECTACULAR_SETTINGS).
EVENT_KIND_CHOICES = Event.Kind.choices
