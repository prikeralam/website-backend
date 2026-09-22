from django.contrib import admin

from .models import ContentBlock, Document, PersonProfile, Testimonial


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "created_by", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "slug")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("attribution", "slug", "status", "created_by", "updated_at")
    list_filter = ("status",)
    search_fields = ("attribution", "slug")


@admin.register(PersonProfile)
class PersonProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "slug", "status", "created_by", "updated_at")
    list_filter = ("status", "group")
    search_fields = ("name", "slug")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "document_type", "year", "status", "created_by", "updated_at")
    list_filter = ("status", "document_type", "year")
    search_fields = ("title", "slug")
