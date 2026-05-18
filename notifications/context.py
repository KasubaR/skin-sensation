from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models import prefetch_related_objects
from django.urls import reverse

from bookings.models import Appointment


def _customer_profile(appointment: Appointment):
    return getattr(appointment.customer, 'customer_profile', None)


def _customer_name(appointment: Appointment) -> str:
    profile = _customer_profile(appointment)
    if profile and profile.full_name:
        return profile.full_name
    return appointment.customer.get_full_name() or appointment.customer.get_username()


def _customer_phone(appointment: Appointment) -> str:
    profile = _customer_profile(appointment)
    if profile and profile.phone:
        return profile.phone_display if hasattr(profile, 'phone_display') else profile.phone
    return ''


def _service_lines(appointment: Appointment) -> list[dict]:
    # Ensures line_items and their related service are in the prefetch cache.
    # No-op if the caller already prefetched line_items__treatment; otherwise
    # issues two queries (line_items + service) instead of N+1.
    prefetch_related_objects([appointment], 'line_items__treatment')
    return [
        {'name': line.treatment.name, 'price': line.price_snapshot}
        for line in appointment.line_items.all()
    ]


def appointment_detail_url(appointment: Appointment) -> str:
    path = reverse(
        'appointment_detail',
        kwargs={'booking_reference': appointment.booking_reference},
    )
    site = Site.objects.get_current()
    protocol = settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL
    return f'{protocol}://{site.domain}{path}'


def appointment_email_context(appointment: Appointment) -> dict:
    staff_name = ''
    if appointment.assigned_staff:
        staff_name = appointment.assigned_staff.display_name

    return {
        'appointment': appointment,
        'booking_reference': appointment.booking_reference,
        'customer_name': _customer_name(appointment),
        'customer_phone': _customer_phone(appointment),
        'customer_email': appointment.customer.email or '',
        'appointment_date': appointment.appointment_date,
        'start_time': appointment.start_time,
        'end_time': appointment.end_time,
        'staff_name': staff_name,
        'services': _service_lines(appointment),
        'total_price': appointment.total_price,
        'deposit_amount': appointment.deposit_amount,
        'status': appointment.get_status_display(),
        'spa_phone': settings.SPA_PHONE_DISPLAY,
        'spa_whatsapp_url': f'https://wa.me/{settings.SPA_WHATSAPP_E164}',
        'from_email': settings.DEFAULT_FROM_EMAIL,
        'appointment_url': appointment_detail_url(appointment),
    }
