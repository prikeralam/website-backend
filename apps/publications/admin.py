from django.contrib import admin

from .models import Publication


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "format", "language", "date", "status", "created_by")
    list_filter = ("status", "format", "language")
    search_fields = ("title", "slug", "theme")
