from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from bookings.models import Appointment, AppointmentStatus
from bookings.validators import can_cancel_appointment, can_reschedule_appointment
from notifications.context import appointment_email_context
from payments.customer import can_upload_proof, deposit_outstanding, remaining_balance


def parse_appointment_date(value: str):
    return datetime.strptime(value, '%Y-%m-%d').date()


def parse_start_time(value: str):
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError('Invalid time format.')


def portal_context(appointment: Appointment) -> dict:
    ctx = appointment_email_context(appointment)
    ctx.update({
        'can_cancel': can_cancel_appointment(appointment),
        'can_reschedule': can_reschedule_appointment(appointment),
        'line_items': list(appointment.line_items.all()),  # uses prefetch cache from appointments_queryset
        'payment_status_display': appointment.get_payment_status_display(),
        'status_display': appointment.get_status_display(),
        'payments': list(appointment.payments.all()),
        'can_upload_proof': can_upload_proof(appointment),
        'remaining_balance': remaining_balance(appointment),
        'deposit_outstanding': deposit_outstanding(appointment),
    })
    return ctx


def split_appointments(queryset):
    today = timezone.localdate()
    terminal = (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    )
    upcoming = queryset.filter(
        status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
        appointment_date__gte=today,
    )
    history = queryset.filter(
        Q(appointment_date__lt=today) | Q(status__in=terminal),
    )
    return upcoming, history


def appointments_queryset(user):
    return user.appointments.select_related('assigned_staff').prefetch_related(
        'line_items__treatment',
        'payments',
    )


def services_summary(appointment: Appointment) -> str:
    # Uses prefetch cache when appointment came from appointments_queryset;
    # falls back to a fresh query otherwise (e.g. get_customer_appointment).
    lines = list(appointment.line_items.all())
    if not lines:
        return '—'
    first = lines[0].treatment.name
    if len(lines) > 1:
        return f'{first} +{len(lines) - 1} more'
    return first
