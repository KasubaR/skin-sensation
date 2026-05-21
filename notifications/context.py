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


def contact_message_dashboard_url(contact_message) -> str:
    path = reverse(
        'dashboard:contact_message_detail',
        kwargs={'pk': contact_message.pk},
    )
    site = Site.objects.get_current()
    protocol = settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL
    return f'{protocol}://{site.domain}{path}'


def testimonial_dashboard_url(testimonial) -> str:
    path = reverse(
        'dashboard:testimonial_detail',
        kwargs={'pk': testimonial.pk},
    )
    site = Site.objects.get_current()
    protocol = settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL
    return f'{protocol}://{site.domain}{path}'


def testimonial_email_context(testimonial) -> dict:
    return {
        'testimonial': testimonial,
        'customer_name': testimonial.display_author_name,
        'customer_email': testimonial.customer.email or '',
        'service_name': testimonial.service.name if testimonial.service else 'General',
        'rating': testimonial.rating,
        'title': testimonial.title,
        'review': testimonial.review,
        'status': testimonial.get_status_display(),
        'created_at': testimonial.created_at,
        'dashboard_url': testimonial_dashboard_url(testimonial),
    }


def contact_message_email_context(contact_message) -> dict:
    return {
        'contact_message': contact_message,
        'full_name': contact_message.full_name,
        'email': contact_message.email,
        'phone_number': contact_message.phone_number,
        'subject': contact_message.get_subject_display(),
        'message': contact_message.message,
        'created_at': contact_message.created_at,
        'dashboard_url': contact_message_dashboard_url(contact_message),
    }


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
