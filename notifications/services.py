import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, mail_managers
from django.db import transaction
from django.template.loader import render_to_string

from notifications.context import appointment_email_context
from notifications.models import NotificationChannel, NotificationLog, NotificationStatus

logger = logging.getLogger(__name__)

TEMPLATE_BOOKING_RECEIVED = 'booking_received'
TEMPLATE_STAFF_NEW_BOOKING = 'staff_new_booking'
TEMPLATE_APPOINTMENT_REMINDER = 'appointment_reminder'
TEMPLATE_APPOINTMENT_CANCELLED = 'appointment_cancelled'
TEMPLATE_APPOINTMENT_RESCHEDULED = 'appointment_rescheduled'


def _recipient_email(appointment) -> str | None:
    email = (appointment.customer.email or '').strip()
    return email or None


def _claim_log(appointment, template_key: str, recipient: str, channel=NotificationChannel.EMAIL):
    """
    Atomically reserve a log slot for this (appointment, template_key) pair.
    Returns (log_obj, created). If not created, another process already claimed
    the slot (send in progress or previously sent/failed) — caller should abort.
    """
    with transaction.atomic():
        return NotificationLog.objects.get_or_create(
            appointment=appointment,
            template_key=template_key,
            defaults={
                'channel': channel,
                'recipient': recipient,
                'status': NotificationStatus.FAILED,
                'error_message': 'in-progress',
            },
        )


def _send_html_email(
    appointment,
    template_key: str,
    recipient: str,
    subject_template: str,
    body_html_template: str,
    body_text_template: str,
    extra_context: dict | None = None,
) -> bool:
    log, created = _claim_log(appointment, template_key, recipient)
    if not created:
        return False

    context = appointment_email_context(appointment)
    if extra_context:
        context.update(extra_context)

    try:
        subject = render_to_string(subject_template, context).strip()
        body_html = render_to_string(body_html_template, context)
        body_text = render_to_string(body_text_template, context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(body_html, 'text/html')
        message.send(fail_silently=False)
        log.status = NotificationStatus.SENT
        log.error_message = ''
        log.save(update_fields=['status', 'error_message'])
        return True
    except Exception as exc:
        logger.exception(
            'Failed to send %s email for appointment %s',
            template_key,
            appointment.booking_reference,
        )
        log.error_message = str(exc)
        log.save(update_fields=['error_message'])
        return False


def send_booking_received(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return _send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_BOOKING_RECEIVED,
        recipient=recipient,
        subject_template='notifications/email/booking_received_subject.txt',
        body_html_template='notifications/email/booking_received_body.html',
        body_text_template='notifications/email/booking_received_body.txt',
    )


def send_staff_new_booking(appointment) -> bool:
    manager_email = settings.MANAGERS[0][1] if settings.MANAGERS else ''
    log, created = _claim_log(appointment, TEMPLATE_STAFF_NEW_BOOKING, manager_email)
    if not created:
        return False

    try:
        context = appointment_email_context(appointment)
        subject = render_to_string(
            'notifications/email/staff_new_booking_subject.txt',
            context,
        ).strip()
        body = render_to_string(
            'notifications/email/staff_new_booking_body.txt',
            context,
        )
        mail_managers(subject=subject, message=body, fail_silently=False)
        log.status = NotificationStatus.SENT
        log.error_message = ''
        log.save(update_fields=['status', 'error_message'])
        return True
    except Exception as exc:
        logger.exception(
            'Failed to send staff alert for appointment %s',
            appointment.booking_reference,
        )
        log.error_message = str(exc)
        log.save(update_fields=['error_message'])
        return False


def send_appointment_reminder(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return _send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_APPOINTMENT_REMINDER,
        recipient=recipient,
        subject_template='notifications/email/appointment_reminder_subject.txt',
        body_html_template='notifications/email/appointment_reminder_body.html',
        body_text_template='notifications/email/appointment_reminder_body.txt',
    )


def send_appointment_cancelled(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return _send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_APPOINTMENT_CANCELLED,
        recipient=recipient,
        subject_template='notifications/email/appointment_cancelled_subject.txt',
        body_html_template='notifications/email/appointment_cancelled_body.html',
        body_text_template='notifications/email/appointment_cancelled_body.txt',
    )


def send_appointment_rescheduled(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return _send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_APPOINTMENT_RESCHEDULED,
        recipient=recipient,
        subject_template='notifications/email/appointment_rescheduled_subject.txt',
        body_html_template='notifications/email/appointment_rescheduled_body.html',
        body_text_template='notifications/email/appointment_rescheduled_body.txt',
    )


def notify_booking_created(appointment):
    """Send customer confirmation and staff alert after a new booking."""
    send_booking_received(appointment)
    send_staff_new_booking(appointment)


def notify_appointment_cancelled(appointment):
    send_appointment_cancelled(appointment)


def notify_appointment_rescheduled(appointment):
    send_appointment_rescheduled(appointment)
