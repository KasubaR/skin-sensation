from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Staff
from bookings.models import Appointment, AppointmentStatus, DayOfWeek, StaffAvailability
from bookings.pricing import (
    calculate_appointment_window,
    calculate_total_duration,
    calculate_total_price,
)
from bookings.scheduling import (
    get_available_slots,
    intervals_overlap,
    slot_is_available,
)
from services.models import Service, Treatment

User = get_user_model()


def _make_treatment(
    *,
    service_slug='test-service',
    treatment_slug='test-treatment',
    name='Test Treatment',
    duration_minutes=60,
    price=Decimal('300.00'),
):
    service, _ = Service.objects.get_or_create(
        slug=service_slug,
        defaults={'name': service_slug.replace('-', ' ').title(), 'is_active': True},
    )
    treatment, _ = Treatment.objects.update_or_create(
        slug=treatment_slug,
        defaults={
            'service': service,
            'name': name,
            'duration_minutes': duration_minutes,
            'price': price,
            'is_active': True,
        },
    )
    return treatment


class PricingTests(TestCase):
    def setUp(self):
        self.t1 = _make_treatment(
            treatment_slug='facial-express',
            name='Express Facial',
            price=Decimal('300.00'),
        )
        self.t2 = _make_treatment(
            treatment_slug='facial-deep',
            name='Deep Cleansing',
            price=Decimal('400.00'),
        )

    def test_calculate_total_price_and_duration(self):
        treatments = [self.t1, self.t2]
        self.assertEqual(calculate_total_price(treatments), Decimal('700.00'))
        self.assertEqual(calculate_total_duration(treatments), 120)

    def test_appointment_window_includes_buffer_and_deposit(self):
        window = calculate_appointment_window([self.t1])
        self.assertEqual(window['total_duration'], 60)
        self.assertEqual(window['buffer_minutes'], 15)
        self.assertEqual(window['appointment_minutes'], 75)
        self.assertEqual(window['deposit_amount'], Decimal('60'))


class SchedulingTests(TestCase):
    def setUp(self):
        self.treatment = _make_treatment(
            service_slug='massage-therapy',
            treatment_slug='massage-swedish',
            name='Swedish Massage',
            price=Decimal('400.00'),
        )
        self.user = User.objects.create_user(username='staff_t', password='x')
        self.staff = Staff.objects.create(user=self.user, display_name='Tendai K.')
        self.staff.treatments.add(self.treatment)
        for day in range(6):
            StaffAvailability.objects.create(
                staff=self.staff,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(18, 0),
                is_off_day=False,
            )
        self.booking_date = date.today() + timedelta(days=1)
        while self.booking_date.weekday() == 6:
            self.booking_date += timedelta(days=1)

    def test_intervals_overlap(self):
        self.assertTrue(intervals_overlap(time(9, 0), time(10, 0), time(9, 30), time(10, 30)))
        self.assertFalse(intervals_overlap(time(9, 0), time(10, 0), time(10, 0), time(11, 0)))

    def test_slot_removed_after_booking(self):
        result = get_available_slots(
            appointment_date=self.booking_date,
            service_ids=[self.treatment.pk],
            staff_id=self.staff.pk,
        )
        starts = [s['start'] for s in result['slots']]
        self.assertIn('09:00', starts)

        Appointment.objects.create(
            customer=User.objects.create_user(username='cust1', password='x'),
            appointment_date=self.booking_date,
            start_time=time(9, 0),
            end_time=time(10, 15),
            total_duration=60,
            total_price=Decimal('400.00'),
            assigned_staff=self.staff,
            status=AppointmentStatus.CONFIRMED,
        )

        result_after = get_available_slots(
            appointment_date=self.booking_date,
            service_ids=[self.treatment.pk],
            staff_id=self.staff.pk,
        )
        starts_after = [s['start'] for s in result_after['slots']]
        self.assertNotIn('09:00', starts_after)

    def test_slot_is_available_helper(self):
        treatments = [self.treatment]
        self.assertTrue(
            slot_is_available(
                staff=self.staff,
                appointment_date=self.booking_date,
                start_time=time(10, 0),
                services=treatments,
            )
        )

    def test_exclude_appointment_allows_same_slot_reschedule(self):
        customer = User.objects.create_user(username='cust_resched', password='x')
        appt = Appointment.objects.create(
            customer=customer,
            appointment_date=self.booking_date,
            start_time=time(9, 0),
            end_time=time(10, 15),
            total_duration=60,
            total_price=Decimal('400.00'),
            assigned_staff=self.staff,
            status=AppointmentStatus.CONFIRMED,
        )
        treatments = [self.treatment]
        self.assertTrue(
            slot_is_available(
                staff=self.staff,
                appointment_date=self.booking_date,
                start_time=time(9, 0),
                services=treatments,
                exclude_appointment_id=appt.pk,
            )
        )
        self.assertFalse(
            slot_is_available(
                staff=self.staff,
                appointment_date=self.booking_date,
                start_time=time(9, 0),
                services=treatments,
            )
        )


class AppointmentApiTests(TestCase):
    def setUp(self):
        self.treatment = _make_treatment(
            service_slug='nail-treatment',
            treatment_slug='nails-gel',
            name='Gel Manicure',
            price=Decimal('180.00'),
        )
        user = User.objects.create_user(username='staff_n', password='x')
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

    def _post_appointment(self, start_time='10:00'):
        return self.client.post(
            reverse('bookings:create_appointment'),
            data={
                'service_ids': [self.treatment.pk],
                'staff_id': self.staff.pk,
                'appointment_date': self.booking_date.isoformat(),
                'start_time': start_time,
                'full_name': 'Jane Doe',
                'phone': '0977123456',
                'email': 'jane@example.com',
            },
            content_type='application/json',
        )

    def test_create_appointment_success(self):
        response = self._post_appointment()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ref = data['booking_reference']
        self.assertEqual(len(ref), 12)
        int(ref, 16)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_reference_unique_per_appointment(self):
        r1 = self._post_appointment('10:00')
        r2 = self._post_appointment('12:00')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertNotEqual(
            r1.json()['booking_reference'],
            r2.json()['booking_reference'],
        )

    def test_double_booking_returns_409(self):
        first = self._post_appointment('11:00')
        self.assertEqual(first.status_code, 200)
        second = self._post_appointment('11:00')
        self.assertEqual(second.status_code, 409)
