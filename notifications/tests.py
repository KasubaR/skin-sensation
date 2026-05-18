from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, Staff
from bookings.models import Appointment, AppointmentStatus, DayOfWeek, StaffAvailability
from notifications.models import NotificationLog, NotificationStatus
from notifications.services import (
    TEMPLATE_APPOINTMENT_CONFIRMED,
    TEMPLATE_APPOINTMENT_REMINDER,
    TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
    TEMPLATE_BOOKING_RECEIVED,
    TEMPLATE_STAFF_NEW_BOOKING,
    notify_appointment_rescheduled,
    notify_booking_created,
    send_appointment_confirmed,
    send_appointment_reminder,
)
from services.models import Service, Treatment

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificationServiceTests(TestCase):
    def setUp(self):
        parent = Service.objects.create(name='Facials', slug='facials-test', is_active=True)
        self.treatment = Treatment.objects.create(
            service=parent,
            name='Express Facial',
            slug='facial-express-test',
            duration_minutes=60,
            price=Decimal('300.00'),
            is_active=True,
        )
        staff_user = User.objects.create_user(username='staff_notify', password='x')
        self.staff = Staff.objects.create(user=staff_user, display_name='Tendai K.')
        self.staff.treatments.add(self.treatment)

        self.customer = User.objects.create_user(
            username='cust_notify',
            email='customer@example.com',
            password='x',
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name='Jane Doe',
            phone='0977123456',
        )

        self.booking_date = date.today() + timedelta(days=3)
        self.appointment = Appointment.objects.create(
            customer=self.customer,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 15),
            total_duration=60,
            total_price=Decimal('300.00'),
            deposit_amount=Decimal('60.00'),
            assigned_staff=self.staff,
            status=AppointmentStatus.PENDING,
        )
        self.appointment.line_items.create(
            treatment=self.treatment,
            price_snapshot=self.treatment.price,
            duration_snapshot=self.treatment.duration_minutes,
        )

    def test_notify_booking_created_sends_customer_and_manager_emails(self):
        notify_booking_created(self.appointment)

        self.assertEqual(len(mail.outbox), 2)
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any(self.appointment.booking_reference in s for s in subjects))
        customer_mail = next(m for m in mail.outbox if 'customer@example.com' in m.to)
        self.assertIn(self.appointment.booking_reference, customer_mail.body)

        self.assertEqual(
            NotificationLog.objects.filter(status=NotificationStatus.SENT).count(),
            2,
        )

    def test_notify_booking_created_skips_customer_without_email(self):
        self.customer.email = ''
        self.customer.save(update_fields=['email'])
        mail.outbox.clear()

        notify_booking_created(self.appointment)

        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(
            NotificationLog.objects.filter(
                template_key=TEMPLATE_BOOKING_RECEIVED,
            ).exists()
        )
        self.assertTrue(
            NotificationLog.objects.filter(
                template_key=TEMPLATE_STAFF_NEW_BOOKING,
            ).exists()
        )

    def test_notify_booking_created_is_idempotent(self):
        notify_booking_created(self.appointment)
        first_count = len(mail.outbox)
        notify_booking_created(self.appointment)
        self.assertEqual(len(mail.outbox), first_count)
        self.assertEqual(NotificationLog.objects.count(), 2)

    def test_send_appointment_reminder(self):
        send_appointment_reminder(self.appointment)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.appointment.booking_reference, mail.outbox[0].body)
        self.assertIn('customer@example.com', mail.outbox[0].to)
        self.assertTrue(
            NotificationLog.objects.filter(
                template_key=TEMPLATE_APPOINTMENT_REMINDER,
                status=NotificationStatus.SENT,
            ).exists()
        )

    def test_failed_reminder_can_be_retried(self):
        NotificationLog.objects.create(
            appointment=self.appointment,
            template_key=TEMPLATE_APPOINTMENT_REMINDER,
            recipient='customer@example.com',
            status=NotificationStatus.FAILED,
            error_message='smtp error',
        )
        mail.outbox.clear()
        self.assertTrue(send_appointment_reminder(self.appointment))
        self.assertEqual(len(mail.outbox), 1)
        log = NotificationLog.objects.get(
            appointment=self.appointment,
            template_key=TEMPLATE_APPOINTMENT_REMINDER,
        )
        self.assertEqual(log.status, NotificationStatus.SENT)

    def test_send_appointment_confirmed(self):
        send_appointment_confirmed(self.appointment)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('confirmed', mail.outbox[0].body.lower())
        self.assertTrue(
            NotificationLog.objects.filter(
                template_key=TEMPLATE_APPOINTMENT_CONFIRMED,
                status=NotificationStatus.SENT,
            ).exists()
        )

    def test_reschedule_clears_reminder_logs(self):
        NotificationLog.objects.create(
            appointment=self.appointment,
            template_key=TEMPLATE_APPOINTMENT_REMINDER,
            recipient='customer@example.com',
            status=NotificationStatus.SENT,
        )
        NotificationLog.objects.create(
            appointment=self.appointment,
            template_key=TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
            recipient='customer@example.com',
            status=NotificationStatus.SENT,
        )
        mail.outbox.clear()
        notify_appointment_rescheduled(self.appointment)
        self.assertFalse(
            NotificationLog.objects.filter(
                template_key__in=(
                    TEMPLATE_APPOINTMENT_REMINDER,
                    TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
                ),
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReminderCommandTests(TestCase):
    def setUp(self):
        parent = Service.objects.create(name='Nails', slug='nails-remind', is_active=True)
        self.treatment = Treatment.objects.create(
            service=parent,
            name='Gel Manicure',
            slug='nails-gel-remind',
            duration_minutes=60,
            price=Decimal('180.00'),
            is_active=True,
        )
        self.customer = User.objects.create_user(
            username='remind_cust',
            email='remind@example.com',
            password='x',
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name='Remind Me',
            phone='0977000001',
        )

    def test_command_sends_for_tomorrow_appointments(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        appointment = Appointment.objects.create(
            customer=self.customer,
            appointment_date=tomorrow,
            start_time=time(14, 0),
            end_time=time(15, 15),
            total_duration=60,
            total_price=Decimal('180.00'),
            deposit_amount=Decimal('50.00'),
            status=AppointmentStatus.CONFIRMED,
        )
        appointment.line_items.create(
            treatment=self.treatment,
            price_snapshot=self.treatment.price,
            duration_snapshot=self.treatment.duration_minutes,
        )

        out = StringIO()
        call_command('send_appointment_reminders', stdout=out)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(appointment.booking_reference, mail.outbox[0].body)

    def test_command_dry_run_does_not_send(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        Appointment.objects.create(
            customer=self.customer,
            appointment_date=tomorrow,
            start_time=time(14, 0),
            end_time=time(15, 15),
            total_duration=60,
            total_price=Decimal('180.00'),
            status=AppointmentStatus.PENDING,
        )
        out = StringIO()
        call_command('send_appointment_reminders', '--dry-run', stdout=out)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('Would remind', out.getvalue())

    def test_same_day_command_sends_for_today(self):
        today = timezone.localdate()
        appointment = Appointment.objects.create(
            customer=self.customer,
            appointment_date=today,
            start_time=time(10, 0),
            end_time=time(11, 15),
            total_duration=60,
            total_price=Decimal('180.00'),
            deposit_amount=Decimal('50.00'),
            status=AppointmentStatus.CONFIRMED,
        )
        appointment.line_items.create(
            treatment=self.treatment,
            price_snapshot=self.treatment.price,
            duration_snapshot=self.treatment.duration_minutes,
        )
        call_command('send_same_day_reminders')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('today', mail.outbox[0].body.lower())
        self.assertTrue(
            NotificationLog.objects.filter(
                template_key=TEMPLATE_APPOINTMENT_REMINDER_SAME_DAY,
                status=NotificationStatus.SENT,
            ).exists()
        )

    def test_failed_reminder_retried_by_command(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        appointment = Appointment.objects.create(
            customer=self.customer,
            appointment_date=tomorrow,
            start_time=time(14, 0),
            end_time=time(15, 15),
            total_duration=60,
            total_price=Decimal('180.00'),
            status=AppointmentStatus.PENDING,
        )
        NotificationLog.objects.create(
            appointment=appointment,
            template_key=TEMPLATE_APPOINTMENT_REMINDER,
            recipient='remind@example.com',
            status=NotificationStatus.FAILED,
            error_message='temporary failure',
        )
        mail.outbox.clear()
        call_command('send_appointment_reminders')
        self.assertEqual(len(mail.outbox), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BookingNotificationIntegrationTests(TestCase):
    def setUp(self):
        parent = Service.objects.create(name='Nails', slug='nails-int', is_active=True)
        self.treatment = Treatment.objects.create(
            service=parent,
            name='Gel Manicure',
            slug='nails-gel-int',
            duration_minutes=60,
            price=Decimal('180.00'),
            is_active=True,
        )
        user = User.objects.create_user(username='staff_int', password='x')
        self.staff = Staff.objects.create(user=user, display_name='Nomsa B.')
        self.staff.treatments.add(self.treatment)
        StaffAvailability.objects.create(
            staff=self.staff,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(18, 0),
            is_off_day=False,
        )
        self.client = Client()
        self.booking_date = date.today() + timedelta(days=7)
        while self.booking_date.weekday() != DayOfWeek.MONDAY:
            self.booking_date += timedelta(days=1)

    def test_create_appointment_sends_notifications(self):
        response = self.client.post(
            reverse('bookings:create_appointment'),
            data={
                'service_ids': [self.treatment.pk],
                'staff_id': self.staff.pk,
                'appointment_date': self.booking_date.isoformat(),
                'start_time': '10:00',
                'full_name': 'Jane Doe',
                'phone': '0977123456',
                'email': 'jane@example.com',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ref = data['booking_reference']
        self.assertEqual(len(ref), 12)
        int(ref, 16)

        self.assertEqual(len(mail.outbox), 2)
        recipients = [m.to[0] for m in mail.outbox]
        self.assertIn('jane@example.com', recipients)
        manager_emails = [addr for addr in recipients if addr not in ('jane@example.com',)]
        self.assertTrue(manager_emails, 'Expected a staff/manager notification email')
        self.assertTrue(NotificationLog.objects.filter(recipient__icontains='jane').exists())

    def test_booking_references_are_unique(self):
        payload = {
            'service_ids': [self.treatment.pk],
            'staff_id': self.staff.pk,
            'appointment_date': self.booking_date.isoformat(),
            'start_time': '11:00',
            'full_name': 'Jane Doe',
            'phone': '0977123456',
            'email': 'jane@example.com',
        }
        r1 = self.client.post(
            reverse('bookings:create_appointment'),
            data=payload,
            content_type='application/json',
        )
        payload['start_time'] = '14:00'
        payload['email'] = 'jane2@example.com'
        r2 = self.client.post(
            reverse('bookings:create_appointment'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertNotEqual(
            r1.json()['booking_reference'],
            r2.json()['booking_reference'],
        )
