from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, User


@admin.register(User)
class PRIUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("PRI role", {"fields": ("role",)}),)
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = UserAdmin.list_filter + ("role",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "module", "action", "target")
    list_filter = ("module", "action")
    readonly_fields = ("actor", "module", "action", "target", "metadata", "timestamp")
