from django.contrib import admin

from communications.models import Announcement, BusinessInformation, ContactMessage


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'label', 'is_active', 'starts_at', 'ends_at', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('title', 'body', 'label')


@admin.register(BusinessInformation)
class BusinessInformationAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not BusinessInformation.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('full_name', 'email', 'subject', 'message')
    readonly_fields = (
        'full_name',
        'email',
        'phone_number',
        'subject',
        'message',
        'created_at',
    )

    def has_add_permission(self, request):
        return False
