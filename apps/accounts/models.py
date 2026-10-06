from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Role(models.TextChoices):
    PUBLIC = "public", "Donor / Visitor"
    RESEARCHER = "researcher", "Researcher"
    EDITOR = "editor", "Editor"
    FELLOW = "fellow", "Intern / Fellow"
    ADMIN = "admin", "Admin"


class PRIUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Admin-site rights follow the role (User.save), so a superuser has to be an admin.
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PUBLIC)
    # Set when an admin creates the account with a temporary password; cleared once the user sets their own.
    must_change_password = models.BooleanField(default=False)

    objects = PRIUserManager()

    def save(self, *args, **kwargs):
        # The role is the single source of truth for Django admin access, whichever path changed it
        # (API, admin site, seed), so the two permission systems can't disagree.
        self.is_staff = self.is_superuser = self.role == Role.ADMIN
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {*update_fields, "is_staff", "is_superuser"}
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_entries")
    module = models.CharField(max_length=50)
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=200)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
