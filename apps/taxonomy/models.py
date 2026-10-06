from django.core.exceptions import ValidationError
from django.db import models


class Theme(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subthemes"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="unique_theme_name_per_parent"),
        ]

    def clean(self):
        if self.parent_id == self.pk:
            raise ValidationError({"parent": "A theme cannot be its own parent."})
        if self.parent_id and self.parent.parent_id is not None:
            raise ValidationError({"parent": "A sub-theme's parent must itself be a top-level theme (max 2 levels)."})

    def __str__(self):
        return f"{self.parent.name} / {self.name}" if self.parent_id else self.name
