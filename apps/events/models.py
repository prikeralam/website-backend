from django.contrib.postgres.fields import ArrayField
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

    class Mode(models.TextChoices):
        IN_PERSON = "in_person", "In person"
        ONLINE = "online", "Online"
        HYBRID = "hybrid", "Hybrid"

    # Times are local (India); the site shows them as entered.
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    mode = models.CharField(max_length=20, choices=Mode.choices, blank=True)
    # Shown instead of the exact date while it isn't fixed ("December 2026, 3rd or 4th week"); start_date still
    # orders events and decides whether one is upcoming.
    date_note = models.CharField(max_length=200, blank=True)
    # One item per entry. Speakers read "Role: Name (detail)"; a focus area may lead with "Heading: ".
    collaborators = ArrayField(models.CharField(max_length=500), blank=True, default=list)
    speakers = ArrayField(models.CharField(max_length=500), blank=True, default=list)
    focus_areas = ArrayField(models.CharField(max_length=500), blank=True, default=list)

    class Meta(WorkflowMixin.Meta):
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return self.title


class EventImage(models.Model):
    """A photo in an event's gallery. The event's own `image` stays its cover on cards."""

    MAX_PER_EVENT = 20

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to="events/gallery/", validators=IMAGE_VALIDATORS)
    caption = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.event.slug} photo {self.pk}"


# Module-level names for the API schema's enum overrides (settings.SPECTACULAR_SETTINGS).
EVENT_KIND_CHOICES = Event.Kind.choices
EVENT_MODE_CHOICES = Event.Mode.choices
