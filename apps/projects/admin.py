from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "created_by", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "slug")
