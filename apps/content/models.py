from django.db import models

from apps.workflow.models import WorkflowMixin
from apps.workflow.uploads import IMAGE_VALIDATORS


class ContentBlock(WorkflowMixin):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    body = models.TextField()
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=300, blank=True)

    def save(self, *args, **kwargs):
        if not self.seo_title:
            self.seo_title = self.title[:200]
        if not self.seo_description:
            self.seo_description = self.body[:297] + "..." if len(self.body) > 300 else self.body
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Testimonial(WorkflowMixin):
    slug = models.SlugField(unique=True)
    quote = models.TextField()
    attribution = models.CharField(max_length=200)
    role = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.attribution


class PersonProfile(WorkflowMixin):
    GROUP_CHOICES = [
        ("team", "Team"),
        ("patron", "Patron"),
        ("advisory", "Advisory"),
        ("executive", "Executive"),
        ("fellow", "Fellow"),
        ("past-fellow", "Past Fellow"),
        ("author", "Author"),
        ("partner", "Partner"),
    ]
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    role_title = models.CharField(max_length=200)
    group = models.CharField(max_length=20, choices=GROUP_CHOICES)
    bio = models.TextField(blank=True)
    photo_url = models.URLField(blank=True)
    # An uploaded photo wins over photo_url when both are set.
    photo = models.FileField(upload_to="people/", blank=True, validators=IMAGE_VALIDATORS)
    # Public contact links shown on the people pages; both optional.
    linkedin_url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    # The person's or institution's own site; partners link to it.
    website_url = models.URLField(blank=True)
    # Staff set the order people appear in on the public pages: lowest first, then oldest first.
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta(WorkflowMixin.Meta):
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.name


class Document(WorkflowMixin):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="documents/")
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=50, blank=True)
    year = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.title
