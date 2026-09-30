from django.contrib import admin

from .models import AccessRequest, Collection, Dashboard, Dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "format", "sub_theme", "visibility", "status", "created_by")
    list_filter = ("status", "format", "visibility", "sub_theme")
    search_fields = ("title", "slug")


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "embed_type", "theme", "status", "created_by")
    list_filter = ("status", "embed_type", "theme")
    search_fields = ("title", "slug")


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "dataset", "status", "requested_at", "reviewed_by")
    list_filter = ("status",)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "slug")
    filter_horizontal = ("datasets",)
