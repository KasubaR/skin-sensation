from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'appointment',
        'payment_method',
        'amount',
        'status',
        'payment_reference',
        'verified_by',
        'verified_at',
        'created_at',
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('payment_reference', 'appointment__booking_reference')
    raw_id_fields = ('appointment', 'verified_by')
    date_hierarchy = 'created_at'
