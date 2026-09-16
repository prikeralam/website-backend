from django.db import models

from apps.workflow.models import WorkflowMixin


class ContentBlock(WorkflowMixin):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    body = models.TextField()
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=300, blank=True)

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

    def __str__(self):
        return self.name


class Document(WorkflowMixin):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="documents/")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title
