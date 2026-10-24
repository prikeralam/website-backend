from django.contrib import admin

from .models import AccessRequest, Collection, Dashboard, Dataset, DatasetRelease, DatasetReleaseFile


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


class DatasetReleaseFileInline(admin.TabularInline):
    model = DatasetReleaseFile
    extra = 0
    readonly_fields = ("format", "file", "size", "sha256", "created_at")


@admin.register(DatasetRelease)
class DatasetReleaseAdmin(admin.ModelAdmin):
    # Read-mostly: releases move through the API's transition endpoint, which applies the gate and the audit log.
    list_display = ("dataset", "version", "status", "created_by", "published_at")
    list_filter = ("status",)
    search_fields = ("dataset__slug", "dataset__code", "version")
    readonly_fields = ("dataset", "version", "status", "format", "metadata", "row_count", "column_count", "columns",
                       "created_by", "approved_by", "approved_at", "published_at", "created_at", "updated_at")
    inlines = [DatasetReleaseFileInline]
