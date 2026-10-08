from django.contrib import admin

from .models import Application, JobOpening


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ("title", "rolling", "deadline", "display_order", "status")
    list_filter = ("status", "rolling")
    search_fields = ("title", "slug")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "kind", "job", "status", "created_at")
    list_filter = ("status", "kind")
    search_fields = ("full_name", "email")
