from django.db.models import Count
from django.utils import timezone

from bookings.models import Appointment, AppointmentService, AppointmentStatus
from payments.models import Payment, PaymentStatus


def _appointment_queryset(user):
    return user.appointments.select_related('assigned_staff').prefetch_related(
        'line_items__treatment',
        'payments',
    )


def get_upcoming_appointment(user):
    today = timezone.localdate()
    return (
        _appointment_queryset(user)
        .filter(
            status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
            appointment_date__gte=today,
        )
        .order_by('appointment_date', 'start_time')
        .first()
    )


def get_pending_payments(user):
    return Payment.objects.filter(
        appointment__customer=user,
        status=PaymentStatus.PENDING,
    ).select_related('appointment')


def get_total_visits(user) -> int:
    return user.appointments.filter(status=AppointmentStatus.COMPLETED).count()


def get_favorite_service(user):
    completed_ids = user.appointments.filter(
        status=AppointmentStatus.COMPLETED,
    ).values_list('id', flat=True)
    if not completed_ids:
        return None

    top = (
        AppointmentService.objects.filter(appointment_id__in=completed_ids)
        .values('treatment__name')
        .annotate(count=Count('treatment_id'))
        .order_by('-count')
        .first()
    )
    if not top:
        return None
    return top['treatment__name']


def get_recent_bookings(user, limit=5):
    today = timezone.localdate()
    terminal = (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    )
    from django.db.models import Q

    return (
        _appointment_queryset(user)
        .filter(Q(appointment_date__lt=today) | Q(status__in=terminal))
        .order_by('-appointment_date', '-start_time')[:limit]
    )


def get_dashboard_context(user) -> dict:
    return {
        'upcoming_appointment': get_upcoming_appointment(user),
        'pending_payments': get_pending_payments(user),
        'pending_payment_count': get_pending_payments(user).count(),
        'total_visits': get_total_visits(user),
        'favorite_service': get_favorite_service(user),
        'recent_bookings': get_recent_bookings(user),
    }
