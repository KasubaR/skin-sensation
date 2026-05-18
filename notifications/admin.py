from django.contrib import admin

from notifications.models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        'sent_at',
        'template_key',
        'recipient',
        'status',
        'appointment',
    )
    date_hierarchy = 'sent_at'
    list_filter = ('template_key', 'status', 'channel')
    search_fields = (
        'recipient',
        'appointment__booking_reference',
    )
    readonly_fields = (
        'appointment',
        'channel',
        'template_key',
        'recipient',
        'status',
        'sent_at',
        'error_message',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
