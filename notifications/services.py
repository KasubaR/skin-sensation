import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import mail_managers
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from notifications.context import (
    appointment_email_context,
    contact_message_email_context,
    testimonial_email_context,
)
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


def send_guest_claim_account(appointment) -> bool:
    """Send a 'set your password' email to a guest who just booked."""
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        return False

    customer = appointment.customer
    recipient = (customer.email or '').strip()
    if not recipient:
        return False

    # Only send to accounts with no usable password (i.e. guests)
    if customer.has_usable_password():
        return False

    try:
        from django.contrib.sites.models import Site
        uid = urlsafe_base64_encode(force_bytes(customer.pk))
        token = default_token_generator.make_token(customer)
        site = Site.objects.get_current()
        protocol = settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL
        claim_url = f'{protocol}://{site.domain}/accounts/password/reset/confirm/{uid}/{token}/'

        customer_name = (
            customer.get_full_name()
            or getattr(getattr(customer, 'customer_profile', None), 'full_name', '')
            or customer.email
        )
        context = {
            'customer_name': customer_name,
            'booking_reference': appointment.booking_reference,
            'claim_url': claim_url,
            'from_email': settings.DEFAULT_FROM_EMAIL,
        }
        subject = render_to_string(
            'notifications/email/guest_claim_subject.txt', context
        ).strip()
        body_text = render_to_string(
            'notifications/email/guest_claim_body.txt', context
        )
        body_html = render_to_string(
            'notifications/email/guest_claim_body.html', context
        )

        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        msg.attach_alternative(body_html, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception(
            'Failed to send guest claim email for appointment %s',
            appointment.booking_reference,
        )
        return False


def notify_booking_created(appointment):
    """Send customer confirmation and staff alert after a new booking."""
    send_booking_received(appointment)
    send_staff_new_booking(appointment)
    send_guest_claim_account(appointment)


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


def send_review_submitted_notification(testimonial) -> bool:
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        return False
    if not settings.MANAGERS:
        return False

    try:
        context = testimonial_email_context(testimonial)
        subject = render_to_string(
            'notifications/email/review_submitted_subject.txt',
            context,
        ).strip()
        body_text = render_to_string(
            'notifications/email/review_submitted_body.txt',
            context,
        )
        body_html = render_to_string(
            'notifications/email/review_submitted_body.html',
            context,
        )
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email for _, email in settings.MANAGERS],
        )
        msg.attach_alternative(body_html, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception(
            'Failed to send review notification for testimonial pk=%s',
            testimonial.pk,
        )
        return False


def send_review_approved_email(testimonial) -> bool:
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        return False

    recipient = (testimonial.customer.email or '').strip()
    if not recipient:
        return False

    try:
        context = testimonial_email_context(testimonial)
        subject = render_to_string(
            'notifications/email/review_approved_subject.txt',
            context,
        ).strip()
        body_text = render_to_string(
            'notifications/email/review_approved_body.txt',
            context,
        )
        body_html = render_to_string(
            'notifications/email/review_approved_body.html',
            context,
        )
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        msg.attach_alternative(body_html, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception(
            'Failed to send review approved email for testimonial pk=%s',
            testimonial.pk,
        )
        return False


def send_contact_notification(contact_message) -> bool:
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        return False
    if not settings.MANAGERS:
        return False

    try:
        context = contact_message_email_context(contact_message)
        subject = render_to_string(
            'notifications/email/contact_received_subject.txt',
            context,
        ).strip()
        body_text = render_to_string(
            'notifications/email/contact_received_body.txt',
            context,
        )
        body_html = render_to_string(
            'notifications/email/contact_received_body.html',
            context,
        )
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email for _, email in settings.MANAGERS],
        )
        msg.attach_alternative(body_html, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception(
            'Failed to send contact notification for message pk=%s',
            contact_message.pk,
        )
        return False
