from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "start_date", "status")
    list_filter = ("status", "kind")
    search_fields = ("title", "slug")
