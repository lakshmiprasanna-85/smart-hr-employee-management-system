from django.contrib import admin

from .models import AuditEvent, NotificationLog


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "entity_type", "entity_id")
    list_filter = ("action", "entity_type")
    readonly_fields = ("actor", "action", "entity_type", "entity_id", "changes", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "notification_type", "recipient_email", "status")
    list_filter = ("status", "notification_type")
