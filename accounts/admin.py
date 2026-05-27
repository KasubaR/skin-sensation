from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomerNote, CustomerProfile, Staff

User = get_user_model()


class StaffInline(admin.StackedInline):
    model = Staff
    can_delete = False
    verbose_name = 'Staff profile'
    verbose_name_plural = 'Staff profile'
    filter_horizontal = ('treatments',)
    fields = ('display_name', 'specialization', 'bio', 'image', 'is_available', 'treatments')


class UserAdmin(BaseUserAdmin):
    inlines = (StaffInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'specialization', 'is_available')
    list_filter = ('is_available',)
    search_fields = ('display_name', 'specialization', 'user__username', 'user__email')
    raw_id_fields = ('user',)
    filter_horizontal = ('treatments',)


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ('customer', 'author', 'created_at')
    search_fields = ('body', 'customer__email', 'customer__username')
    raw_id_fields = ('customer', 'author')


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'loyalty_points', 'user')
    search_fields = ('full_name', 'phone', 'user__username', 'user__email')
    raw_id_fields = ('user',)
