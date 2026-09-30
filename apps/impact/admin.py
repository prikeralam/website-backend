from django.contrib import admin

from .models import Mention, Recognition


@admin.register(Mention)
class MentionAdmin(admin.ModelAdmin):
    list_display = ("title", "publisher", "kind", "date", "status")
    list_filter = ("status", "kind")
    search_fields = ("title", "publisher", "slug")


@admin.register(Recognition)
class RecognitionAdmin(admin.ModelAdmin):
    list_display = ("title", "awarded_by", "year", "status")
    list_filter = ("status",)
    search_fields = ("title", "awarded_by", "slug")
