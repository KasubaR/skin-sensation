from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, Staff
from bookings.models import Appointment, AppointmentService, AppointmentStatus, DayOfWeek, StaffAvailability
from bookings.validators import CANCELLATION_NOTICE_HOURS, can_modify_appointment
from bookings.portal import PortalError, cancel_appointment, reschedule_appointment
from services.models import Service, Treatment

User = get_user_model()


class PortalPolicyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='policy_user',
            email='policy@example.com',
            password='testpass123',
        )
        self.appointment = Appointment.objects.create(
            customer=self.user,
            appointment_date=date.today() + timedelta(days=3),
            start_time=time(10, 0),
            end_time=time(11, 15),
            total_duration=60,
            total_price=Decimal('400.00'),
            status=AppointmentStatus.PENDING,
        )

    def test_can_modify_future_appointment_beyond_notice(self):
        self.assertTrue(can_modify_appointment(self.appointment))

    def test_cannot_modify_past_appointment(self):
        self.appointment.appointment_date = date.today() - timedelta(days=1)
        self.appointment.save(update_fields=['appointment_date'])
        self.assertFalse(can_modify_appointment(self.appointment))

    def test_cannot_modify_completed(self):
        self.appointment.status = AppointmentStatus.COMPLETED
        self.appointment.save(update_fields=['status'])
        self.assertFalse(can_modify_appointment(self.appointment))

    def test_cannot_modify_within_notice_window(self):
        tomorrow = date.today() + timedelta(days=1)
        self.appointment.appointment_date = tomorrow
        self.appointment.start_time = time(10, 0)
        self.appointment.save(update_fields=['appointment_date', 'start_time'])
        with patch('bookings.validators.timezone.now') as mock_now:
            starts = timezone.make_aware(datetime.combine(tomorrow, time(10, 0)))
            mock_now.return_value = starts - timedelta(hours=CANCELLATION_NOTICE_HOURS - 1)
            self.assertFalse(can_modify_appointment(self.appointment))


class PortalViewTests(TestCase):
    def setUp(self):
        parent = Service.objects.create(name='Facials', slug='facials-portal', is_active=True)
        self.treatment = Treatment.objects.create(
            service=parent,
            name='Express Facial',
            slug='facial-portal',
            duration_minutes=60,
            price=Decimal('300.00'),
            is_active=True,
        )
        staff_user = User.objects.create_user(username='staff_portal', password='x')
        self.staff = Staff.objects.create(user=staff_user, display_name='Portal Staff')
        self.staff.treatments.add(self.treatment)
        for day in range(6):
            StaffAvailability.objects.create(
                staff=self.staff,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(18, 0),
                is_off_day=False,
            )

        self.user_a = User.objects.create_user(
            username='user_a',
            email='a@example.com',
            password='testpass123',
        )
        self.user_b = User.objects.create_user(
            username='user_b',
            email='b@example.com',
            password='testpass123',
        )
        CustomerProfile.objects.create(user=self.user_a, full_name='User A', phone='0977111111')

        self.booking_date = date.today() + timedelta(days=5)
        while self.booking_date.weekday() == 6:
            self.booking_date += timedelta(days=1)

        self.appointment = Appointment.objects.create(
            customer=self.user_a,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 15),
            total_duration=60,
            total_price=Decimal('300.00'),
            deposit_amount=Decimal('60.00'),
            status=AppointmentStatus.PENDING,
            assigned_staff=self.staff,
        )
        AppointmentService.objects.create(
            appointment=self.appointment,
            treatment=self.treatment,
            price_snapshot=self.treatment.price,
            duration_snapshot=self.treatment.duration_minutes,
        )
        self.client = Client()

    def test_anonymous_list_redirects_to_login(self):
        response = self.client.get(reverse('appointment_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_appointment_list_filter_completed(self):
        self.client.login(username='user_a', password='testpass123')
        self.appointment.status = AppointmentStatus.COMPLETED
        self.appointment.save(update_fields=['status'])
        response = self.client.get(reverse('appointment_list'), {'filter': 'completed'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.appointment.booking_reference)

    def test_anonymous_detail_redirects_to_login(self):
        response = self.client.get(
            reverse('appointment_detail', kwargs={'booking_reference': self.appointment.booking_reference})
        )
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_view_other_users_appointment(self):
        self.client.login(username='user_b', password='testpass123')
        response = self.client.get(
            reverse('appointment_detail', kwargs={'booking_reference': self.appointment.booking_reference})
        )
        self.assertEqual(response.status_code, 404)

    def test_cancel_appointment_via_portal(self):
        self.client.login(username='user_a', password='testpass123')
        with patch('notifications.services.send_appointment_cancelled', return_value=True):
            response = self.client.post(
                reverse('appointment_cancel', kwargs={'booking_reference': self.appointment.booking_reference}),
            )
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, AppointmentStatus.CANCELLED)

    def test_reschedule_appointment_via_portal(self):
        self.client.login(username='user_a', password='testpass123')
        new_date = self.booking_date + timedelta(days=1)
        while new_date.weekday() == 6:
            new_date += timedelta(days=1)
        with patch('notifications.services.send_appointment_rescheduled', return_value=True):
            response = self.client.post(
                reverse('appointment_reschedule', kwargs={'booking_reference': self.appointment.booking_reference}),
                data={
                    'appointment_date': new_date.isoformat(),
                    'start_time': '14:00',
                    'staff_id': self.staff.pk,
                },
            )
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.appointment_date, new_date)
        self.assertEqual(self.appointment.start_time, time(14, 0))


class PortalServiceTests(TestCase):
    def setUp(self):
        parent = Service.objects.create(name='Facials', slug='facials-svc', is_active=True)
        self.treatment = Treatment.objects.create(
            service=parent,
            name='Express Facial',
            slug='facial-svc',
            duration_minutes=60,
            price=Decimal('300.00'),
            is_active=True,
        )
        staff_user = User.objects.create_user(username='staff_svc', password='x')
        self.staff = Staff.objects.create(user=staff_user, display_name='Svc Staff')
        self.staff.treatments.add(self.treatment)
        for day in range(6):
            StaffAvailability.objects.create(
                staff=self.staff,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(18, 0),
                is_off_day=False,
            )

        self.user = User.objects.create_user(
            username='svc_user',
            email='svc@example.com',
            password='testpass123',
        )
        self.booking_date = date.today() + timedelta(days=4)
        while self.booking_date.weekday() == 6:
            self.booking_date += timedelta(days=1)

        self.appointment = Appointment.objects.create(
            customer=self.user,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 15),
            total_duration=60,
            total_price=Decimal('300.00'),
            status=AppointmentStatus.PENDING,
            assigned_staff=self.staff,
        )
        AppointmentService.objects.create(
            appointment=self.appointment,
            treatment=self.treatment,
            price_snapshot=self.treatment.price,
            duration_snapshot=self.treatment.duration_minutes,
        )

    def test_cancel_raises_when_not_allowed(self):
        self.appointment.appointment_date = date.today() - timedelta(days=1)
        self.appointment.save(update_fields=['appointment_date'])
        with self.assertRaises(PortalError):
            cancel_appointment(self.appointment)

    def test_reschedule_updates_times(self):
        new_date = self.booking_date + timedelta(days=1)
        while new_date.weekday() == 6:
            new_date += timedelta(days=1)
        with patch('notifications.services.send_appointment_rescheduled', return_value=True):
            reschedule_appointment(
                self.appointment,
                new_date=new_date,
                new_start_time=time(14, 0),
                staff_id=self.staff.pk,
            )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.appointment_date, new_date)
        self.assertEqual(self.appointment.start_time, time(14, 0))
