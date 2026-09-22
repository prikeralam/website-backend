from django.contrib import admin

from .models import Publication, PublicationVersion


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "format", "sub_theme", "language", "date", "visibility", "status", "created_by")
    list_filter = ("status", "format", "language", "visibility")
    search_fields = ("title", "slug", "sub_theme__name")


@admin.register(PublicationVersion)
class PublicationVersionAdmin(admin.ModelAdmin):
    list_display = ("publication", "version_number", "is_current", "uploaded_by", "created_at")
    list_filter = ("is_current",)
