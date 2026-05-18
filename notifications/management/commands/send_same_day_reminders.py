from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Appointment, AppointmentStatus
from notifications.models import NotificationLog, NotificationStatus
from notifications.services import (
    TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
    send_same_day_reminder,
)


class Command(BaseCommand):
    help = 'Send same-day email reminders for appointments scheduled today.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List appointments that would receive a reminder without sending email.',
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        reminded_ids = NotificationLog.objects.filter(
            template_key=TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
            status=NotificationStatus.SENT,
        ).values_list('appointment_id', flat=True)

        appointments = (
            Appointment.objects.filter(
                appointment_date=today,
                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED],
            )
            .exclude(pk__in=reminded_ids)
            .select_related('customer', 'assigned_staff')
            .prefetch_related('line_items__treatment')
        )

        total = appointments.count()
        sent = 0
        no_email = 0
        failed = 0

        for appointment in appointments:
            email = (appointment.customer.email or '').strip()
            if not email:
                no_email += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Skip {appointment.booking_reference}: no customer email',
                    )
                )
                continue

            if options['dry_run']:
                self.stdout.write(
                    f'Would remind: {appointment.booking_reference} -> {email}',
                )
                continue

            if send_same_day_reminder(appointment):
                sent += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Sent same-day reminder: {appointment.booking_reference} -> {email}',
                    )
                )
            else:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed same-day reminder: {appointment.booking_reference} -> {email}',
                    )
                )

        if options['dry_run']:
            self.stdout.write(
                self.style.NOTICE(
                    f'Dry run: {total} appointment(s) for {today}.',
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Sent {sent} same-day reminder(s); no_email {no_email}; failed {failed}.',
                ),
            )
