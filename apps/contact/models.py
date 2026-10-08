from django.conf import settings
from django.db import models


class ContactMessage(models.Model):
    """A message sent through the public contact form (the contact slice of Module G)."""

    class Category(models.TextChoices):
        GENERAL = "general", "General Enquiry"
        COLLABORATION = "collaboration", "Collaboration"
        DATA_REQUEST = "data_request", "Data Request"

    class Status(models.TextChoices):
        NEW = "new", "New"
        HANDLED = "handled", "Handled"

    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField(max_length=5000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_category_display()} message from {self.name}"
