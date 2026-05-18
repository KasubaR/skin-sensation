from django.contrib import admin

from .models import CustomerProfile, Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'specialization', 'is_available')
    list_filter = ('is_available',)
    search_fields = ('display_name', 'specialization', 'user__username', 'user__email')
    raw_id_fields = ('user',)
    filter_horizontal = ('treatments',)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'user')
    search_fields = ('full_name', 'phone', 'user__username', 'user__email')
    raw_id_fields = ('user',)
