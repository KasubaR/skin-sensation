import logging

from django.conf import settings
from django.core.mail import mail_managers
from django.template.loader import render_to_string

from notifications.context import appointment_email_context
from notifications.dispatch import prepare_notification_log, send_html_email
from notifications.models import NotificationChannel, NotificationLog, NotificationStatus

logger = logging.getLogger(__name__)

TEMPLATE_BOOKING_RECEIVED = 'booking_received'
TEMPLATE_STAFF_NEW_BOOKING = 'staff_new_booking'
TEMPLATE_APPOINTMENT_REMINDER = 'appointment_reminder'
TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY = 'appointment_reminder_same_day'
TEMPLATE_APPOINTMENT_CONFIRMED = 'appointment_confirmed'
TEMPLATE_APPOINTMENT_CANCELLED = 'appointment_cancelled'
TEMPLATE_APPOINTMENT_RESCHEDULED = 'appointment_rescheduled'
TEMPLATE_PAYMENT_RECEIVED = 'payment_received'
TEMPLATE_PAYMENT_VERIFIED = 'payment_verified'
TEMPLATE_PAYMENT_REJECTED = 'payment_rejected'

REMINDER_TEMPLATE_KEYS = (
    TEMPLATE_APPOINTMENT_REMINDER,
    TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
)


def _recipient_email(appointment):
    email = (appointment.customer.email or '').strip()
    return email or None


def _customer_wants_payment_email(appointment) -> bool:
    profile = getattr(appointment.customer, 'customer_profile', None)
    if profile is None:
        return True
    return profile.wants_email('payments')


def payment_email_context(payment) -> dict:
    ctx = appointment_email_context(payment.appointment)
    ctx.update({
        'payment': payment,
        'payment_amount': payment.amount,
        'payment_method': payment.get_payment_method_display(),
        'payment_reference': payment.payment_reference,
        'payment_status': payment.get_status_display(),
        'rejection_reason': payment.rejection_reason,
    })
    return ctx


def clear_appointment_reminder_logs(appointment) -> int:
    """Remove reminder logs so a rescheduled appointment can receive new reminders."""
    deleted, _ = NotificationLog.objects.filter(
        appointment=appointment,
        template_key__in=REMINDER_TEMPLATE_KEYS,
    ).delete()
    return deleted


def send_booking_received(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_BOOKING_RECEIVED,
        recipient=recipient,
        subject_template='notifications/email/booking_received_subject.txt',
        body_html_template='notifications/email/booking_received_body.html',
        body_text_template='notifications/email/booking_received_body.txt',
    )


def send_staff_new_booking(appointment) -> bool:
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        return False

    manager_email = settings.MANAGERS[0][1] if settings.MANAGERS else ''
    log = prepare_notification_log(
        appointment,
        TEMPLATE_STAFF_NEW_BOOKING,
        manager_email,
    )
    if log is None:
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
        log.status = NotificationStatus.FAILED
        log.error_message = str(exc)
        log.save(update_fields=['status', 'error_message'])
        return False


def send_appointment_reminder(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_APPOINTMENT_REMINDER,
        recipient=recipient,
        subject_template='notifications/email/appointment_reminder_subject.txt',
        body_html_template='notifications/email/appointment_reminder_body.html',
        body_text_template='notifications/email/appointment_reminder_body.txt',
    )


def send_same_day_reminder(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
        recipient=recipient,
        subject_template='notifications/email/appointment_reminder_same_day_subject.txt',
        body_html_template='notifications/email/appointment_reminder_same_day_body.html',
        body_text_template='notifications/email/appointment_reminder_same_day_body.txt',
    )


def send_appointment_confirmed(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_APPOINTMENT_CONFIRMED,
        recipient=recipient,
        subject_template='notifications/email/appointment_confirmed_subject.txt',
        body_html_template='notifications/email/appointment_confirmed_body.html',
        body_text_template='notifications/email/appointment_confirmed_body.txt',
    )


def send_appointment_cancelled(appointment) -> bool:
    recipient = _recipient_email(appointment)
    if not recipient:
        return False

    return send_html_email(
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

    return send_html_email(
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


def notify_appointment_confirmed(appointment):
    send_appointment_confirmed(appointment)


def notify_appointment_cancelled(appointment):
    send_appointment_cancelled(appointment)


def notify_appointment_rescheduled(appointment):
    clear_appointment_reminder_logs(appointment)
    send_appointment_rescheduled(appointment)


def send_payment_received(payment) -> bool:
    appointment = payment.appointment
    recipient = _recipient_email(appointment)
    if not recipient or not _customer_wants_payment_email(appointment):
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_PAYMENT_RECEIVED,
        recipient=recipient,
        subject_template='notifications/email/payment_received_subject.txt',
        body_html_template='notifications/email/payment_received_body.html',
        body_text_template='notifications/email/payment_received_body.txt',
        extra_context=payment_email_context(payment),
    )


def send_payment_verified(payment) -> bool:
    appointment = payment.appointment
    recipient = _recipient_email(appointment)
    if not recipient or not _customer_wants_payment_email(appointment):
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_PAYMENT_VERIFIED,
        recipient=recipient,
        subject_template='notifications/email/payment_verified_subject.txt',
        body_html_template='notifications/email/payment_verified_body.html',
        body_text_template='notifications/email/payment_verified_body.txt',
        extra_context=payment_email_context(payment),
    )


def send_payment_rejected(payment) -> bool:
    appointment = payment.appointment
    recipient = _recipient_email(appointment)
    if not recipient or not _customer_wants_payment_email(appointment):
        return False

    return send_html_email(
        appointment=appointment,
        template_key=TEMPLATE_PAYMENT_REJECTED,
        recipient=recipient,
        subject_template='notifications/email/payment_rejected_subject.txt',
        body_html_template='notifications/email/payment_rejected_body.html',
        body_text_template='notifications/email/payment_rejected_body.txt',
        extra_context=payment_email_context(payment),
    )


def send_staff_payment_received(payment) -> bool:
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        return False

    appointment = payment.appointment
    manager_email = settings.MANAGERS[0][1] if settings.MANAGERS else ''
    log = prepare_notification_log(
        appointment,
        f'{TEMPLATE_PAYMENT_RECEIVED}_staff',
        manager_email,
    )
    if log is None:
        return False

    try:
        context = payment_email_context(payment)
        subject = render_to_string(
            'notifications/email/staff_payment_received_subject.txt',
            context,
        ).strip()
        body = render_to_string(
            'notifications/email/staff_payment_received_body.txt',
            context,
        )
        mail_managers(subject=subject, message=body, fail_silently=False)
        log.status = NotificationStatus.SENT
        log.error_message = ''
        log.save(update_fields=['status', 'error_message'])
        return True
    except Exception as exc:
        logger.exception(
            'Failed to send staff payment alert for appointment %s',
            appointment.booking_reference,
        )
        log.status = NotificationStatus.FAILED
        log.error_message = str(exc)
        log.save(update_fields=['status', 'error_message'])
        return False


def notify_payment_received(payment):
    send_payment_received(payment)
    send_staff_payment_received(payment)


def notify_payment_verified(payment):
    send_payment_verified(payment)


def notify_payment_rejected(payment):
    send_payment_rejected(payment)
