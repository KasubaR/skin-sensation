from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Appointment, AppointmentStatus
from notifications.models import NotificationLog, NotificationStatus
from notifications.services import TEMPLATE_APPOINTMENT_REMINDER, send_appointment_reminder


class Command(BaseCommand):
    help = 'Send day-before email reminders for appointments scheduled tomorrow.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List appointments that would receive a reminder without sending email.',
        )

    def handle(self, *args, **options):
        tomorrow = timezone.localdate() + timedelta(days=1)
        reminded_ids = NotificationLog.objects.filter(
            template_key=TEMPLATE_APPOINTMENT_REMINDER,
            status=NotificationStatus.SENT,
        ).values_list('appointment_id', flat=True)

        appointments = (
            Appointment.objects.filter(
                appointment_date=tomorrow,
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

            if send_appointment_reminder(appointment):
                sent += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Sent reminder: {appointment.booking_reference} -> {email}',
                    )
                )
            else:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed reminder: {appointment.booking_reference} -> {email}',
                    )
                )

        if options['dry_run']:
            self.stdout.write(
                self.style.NOTICE(
                    f'Dry run: {total} appointment(s) for {tomorrow}.',
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Sent {sent} reminder(s); no_email {no_email}; failed {failed}.',
                ),
            )
