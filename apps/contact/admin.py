from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("name", "email", "message")
