from django.contrib import admin

from communications.models import BusinessInformation, ContactMessage


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
