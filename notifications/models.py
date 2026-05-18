from django.db import models


class NotificationChannel(models.TextChoices):
    EMAIL = 'EMAIL', 'Email'
    WHATSAPP = 'WHATSAPP', 'WhatsApp'


class NotificationStatus(models.TextChoices):
    SENT = 'SENT', 'Sent'
    FAILED = 'FAILED', 'Failed'


class NotificationLog(models.Model):
    appointment = models.ForeignKey(
        'bookings.Appointment',
        on_delete=models.CASCADE,
        related_name='notification_logs',
    )
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannel.choices,
        default=NotificationChannel.EMAIL,
    )
    template_key = models.CharField(max_length=64)
    recipient = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=10,
        choices=NotificationStatus.choices,
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']
        constraints = [
            models.UniqueConstraint(
                fields=['appointment', 'template_key'],
                condition=models.Q(status='SENT'),
                name='notifications_log_appt_template_sent_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.template_key} → {self.recipient or "(no recipient)"} ({self.status})'
