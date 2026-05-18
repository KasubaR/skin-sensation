"""
Central notification dispatch. Email uses Django's mail stack (SMTP today;
SendGrid/Mailgun via django-anymail can be wired through EMAIL_BACKEND later).
"""
import logging
from typing import Dict, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from notifications.context import appointment_email_context
from notifications.models import NotificationChannel, NotificationLog, NotificationStatus

logger = logging.getLogger(__name__)


def prepare_notification_log(
    appointment,
    template_key: str,
    recipient: str,
    channel: str = NotificationChannel.EMAIL,
) -> Optional[NotificationLog]:
    """
    Return a log row ready for send, or None if this template was already SENT.
    Reuses the latest non-SENT log for retries after FAILED.
    """
    if NotificationLog.objects.filter(
        appointment=appointment,
        template_key=template_key,
        status=NotificationStatus.SENT,
    ).exists():
        return None

    log = (
        NotificationLog.objects.filter(
            appointment=appointment,
            template_key=template_key,
        )
        .order_by('-sent_at')
        .first()
    )

    if log:
        log.recipient = recipient
        log.channel = channel
        log.status = NotificationStatus.FAILED
        log.error_message = 'in-progress'
        log.save(update_fields=['recipient', 'channel', 'status', 'error_message'])
        return log

    return NotificationLog.objects.create(
        appointment=appointment,
        template_key=template_key,
        channel=channel,
        recipient=recipient,
        status=NotificationStatus.FAILED,
        error_message='in-progress',
    )


def send_html_email(
    *,
    appointment,
    template_key: str,
    recipient: str,
    subject_template: str,
    body_html_template: str,
    body_text_template: str,
    extra_context: Optional[Dict] = None,
) -> bool:
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True):
        logger.info('Email notifications disabled; skip %s', template_key)
        return False

    log = prepare_notification_log(appointment, template_key, recipient)
    if log is None:
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
        log.status = NotificationStatus.FAILED
        log.error_message = str(exc)
        log.save(update_fields=['status', 'error_message'])
        return False
