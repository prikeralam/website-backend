from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    PUBLIC = "public", "Donor / Visitor"
    RESEARCHER = "researcher", "Researcher"
    EDITOR = "editor", "Editor"
    FELLOW = "fellow", "Intern / Fellow"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PUBLIC)


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_entries")
    module = models.CharField(max_length=50)
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=200)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
