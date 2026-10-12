from django.contrib import admin

from .models import Event, EventImage


class EventImageInline(admin.TabularInline):
    model = EventImage
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    inlines = [EventImageInline]
    list_display = ("title", "kind", "start_date", "status")
    list_filter = ("status", "kind")
    search_fields = ("title", "slug")
