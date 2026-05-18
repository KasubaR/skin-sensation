from django.contrib import admin

from .models import Appointment, AppointmentService, StaffAvailability


class AppointmentServiceInline(admin.TabularInline):
    model = AppointmentService
    extra = 0
    raw_id_fields = ('treatment',)


@admin.register(StaffAvailability)
class StaffAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('staff', 'day_of_week', 'start_time', 'end_time', 'is_off_day')
    list_filter = ('day_of_week', 'is_off_day')
    raw_id_fields = ('staff',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        'booking_reference',
        'appointment_date',
        'start_time',
        'end_time',
        'status',
        'payment_status',
        'customer',
        'assigned_staff',
        'created_at',
    )
    list_filter = ('status', 'payment_status', 'appointment_date')
    search_fields = (
        'booking_reference',
        'notes',
        'customer__username',
        'customer__email',
    )
    raw_id_fields = ('customer', 'assigned_staff')
    date_hierarchy = 'appointment_date'
    inlines = [AppointmentServiceInline]


@admin.register(AppointmentService)
class AppointmentServiceAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'treatment', 'price_snapshot', 'duration_snapshot')
    raw_id_fields = ('appointment', 'treatment')
