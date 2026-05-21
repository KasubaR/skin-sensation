from django.contrib import admin

from dashboard.models import StaffActivityLog


@admin.register(StaffActivityLog)
class StaffActivityLogAdmin(admin.ModelAdmin):
  list_display = ('created_at', 'user', 'action', 'message', 'target_type', 'target_id')
  list_filter = ('action',)
  search_fields = ('message', 'target_id')
  readonly_fields = ('user', 'action', 'target_type', 'target_id', 'message', 'created_at')
