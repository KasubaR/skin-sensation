from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import CustomerNote, CustomerProfile, Staff
from bookings.models import (
    Appointment,
    AppointmentPaymentStatus,
    AppointmentService,
    AppointmentStatus,
    DayOfWeek,
    StaffAvailability,
)
from bookings.tests import _make_treatment
from dashboard.appointment_logic import can_transition
from dashboard.models import StaffActivityLog
from dashboard.stats import get_today_appointments_count
from payments.models import Payment, PaymentMethod, PaymentStatus
from payments.services import reject_payment, verify_payment

User = get_user_model()


class StaffAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='manager',
            password='secret',
            is_staff=True,
        )
        self.customer_user = User.objects.create_user(username='cust', password='secret')

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_non_staff_forbidden(self):
        self.client.login(username='cust', password='secret')
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access_dashboard(self):
        self.client.login(username='manager', password='secret')
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Overview')
        self.assertContains(response, "Today's bookings")


class StatusTransitionTests(TestCase):
    def test_allowed_transitions(self):
        self.assertTrue(can_transition(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED))
        self.assertFalse(can_transition(AppointmentStatus.COMPLETED, AppointmentStatus.PENDING))

    def test_staff_status_update(self):
        manager = User.objects.create_user(username='mgr', password='x', is_staff=True)
        customer = User.objects.create_user(username='c1', password='x')
        treatment = _make_treatment()
        appt = Appointment.objects.create(
            customer=customer,
            appointment_date=date.today() + timedelta(days=3),
            start_time=time(10, 0),
            end_time=time(11, 0),
            total_price=Decimal('300'),
            deposit_amount=Decimal('60'),
            status=AppointmentStatus.PENDING,
            payment_status=AppointmentPaymentStatus.UNPAID,
        )
        AppointmentService.objects.create(
            appointment=appt,
            treatment=treatment,
            price_snapshot=treatment.price,
            duration_snapshot=treatment.duration_minutes,
        )
        client = Client()
        client.login(username='mgr', password='x')
        url = reverse('dashboard:appointment_detail', args=[appt.booking_reference])
        response = client.post(url, {'action': 'update_status', 'status': AppointmentStatus.CONFIRMED})
        self.assertEqual(response.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, AppointmentStatus.CONFIRMED)


class CalendarApiTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='mgr2', password='x', is_staff=True)
        self.customer = User.objects.create_user(username='c2', password='x')
        self.treatment = _make_treatment(treatment_slug='cal-treatment')
        self.appt_date = date.today() + timedelta(days=5)
        while self.appt_date.weekday() == 6:
            self.appt_date += timedelta(days=1)

    def test_calendar_api_returns_events_in_range(self):
        appt = Appointment.objects.create(
            customer=self.customer,
            appointment_date=self.appt_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            total_price=Decimal('200'),
            deposit_amount=Decimal('50'),
        )
        client = Client()
        client.login(username='mgr2', password='x')
        url = reverse('dashboard:appointment_calendar_api')
        response = client.get(url, {
            'start': self.appt_date.isoformat(),
            'end': self.appt_date.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], appt.booking_reference)


class CustomerNoteTests(TestCase):
    def test_customer_detail_add_note(self):
        manager = User.objects.create_user(username='mgr3', password='x', is_staff=True)
        customer = User.objects.create_user(username='c3', password='x', email='c3@test.com')
        CustomerProfile.objects.create(user=customer, full_name='Jane Doe', phone='0977123456')
        client = Client()
        client.login(username='mgr3', password='x')
        url = reverse('dashboard:customer_detail', args=[customer.pk])
        response = client.post(url, {'action': 'add_note', 'body': 'Prefers morning slots.'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerNote.objects.filter(customer=customer).count(), 1)


class PaymentVerificationTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='mgr4', password='x', is_staff=True)
        self.customer = User.objects.create_user(username='c4', password='x')
        self.appt = Appointment.objects.create(
            customer=self.customer,
            appointment_date=date.today() + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(10, 0),
            total_price=Decimal('300'),
            deposit_amount=Decimal('60'),
            payment_status=AppointmentPaymentStatus.UNPAID,
        )
        self.payment = Payment.objects.create(
            appointment=self.appt,
            amount=Decimal('60'),
            payment_method=PaymentMethod.OTHER,
            status=PaymentStatus.PENDING,
        )

    def test_verify_payment_updates_appointment(self):
        verify_payment(self.payment, self.manager)
        self.appt.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.VERIFIED)
        self.assertEqual(self.appt.payment_status, AppointmentPaymentStatus.DEPOSIT_PAID)

    def test_reject_payment(self):
        reject_payment(self.payment, self.manager, reason='Invalid proof')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.FAILED)
        self.assertEqual(self.payment.rejection_reason, 'Invalid proof')


class OverviewStatsTests(TestCase):
    def test_today_appointments_excludes_cancelled(self):
        customer = User.objects.create_user(username='stats_c', password='x')
        treatment = _make_treatment(treatment_slug='stats-t')
        today = date.today()
        Appointment.objects.create(
            customer=customer,
            appointment_date=today,
            start_time=time(10, 0),
            end_time=time(11, 0),
            total_price=Decimal('100'),
            status=AppointmentStatus.CONFIRMED,
        )
        Appointment.objects.create(
            customer=customer,
            appointment_date=today,
            start_time=time(14, 0),
            end_time=time(15, 0),
            total_price=Decimal('100'),
            status=AppointmentStatus.CANCELLED,
        )
        self.assertEqual(get_today_appointments_count(), 1)


class PaymentListFilterTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='payfilt', password='x', is_staff=True)
        self.customer = User.objects.create_user(username='payfilt_c', password='x')
        self.appt = Appointment.objects.create(
            customer=self.customer,
            appointment_date=date.today() + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(10, 0),
            total_price=Decimal('300'),
            deposit_amount=Decimal('60'),
        )

    def test_payment_list_verified_filter(self):
        Payment.objects.create(
            appointment=self.appt,
            amount=Decimal('60'),
            status=PaymentStatus.VERIFIED,
        )
        client = Client()
        client.login(username='payfilt', password='x')
        response = client.get(reverse('dashboard:payment_list'), {'status': PaymentStatus.VERIFIED})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verified')


class ActivityLogTests(TestCase):
    def test_verify_payment_creates_activity_from_view(self):
        manager = User.objects.create_user(username='act_mgr', password='x', is_staff=True)
        customer = User.objects.create_user(username='act_c', password='x')
        appt = Appointment.objects.create(
            customer=customer,
            appointment_date=date.today() + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(10, 0),
            total_price=Decimal('300'),
            deposit_amount=Decimal('60'),
        )
        payment = Payment.objects.create(
            appointment=appt,
            amount=Decimal('60'),
            status=PaymentStatus.PENDING,
        )
        client = Client()
        client.login(username='act_mgr', password='x')
        url = reverse('dashboard:payment_detail', args=[payment.pk])
        response = client.post(url, {'action': 'approve'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            StaffActivityLog.objects.filter(
                action=StaffActivityLog.Action.PAYMENT_VERIFIED,
            ).exists()
        )


class ReportsViewTests(TestCase):
    def test_staff_can_access_reports(self):
        manager = User.objects.create_user(username='rep_mgr', password='x', is_staff=True)
        client = Client()
        client.login(username='rep_mgr', password='x')
        response = client.get(reverse('dashboard:reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reports')


class BookingPaymentCreationTests(TestCase):
    def setUp(self):
        self.treatment = _make_treatment(
            service_slug='pay-svc',
            treatment_slug='pay-treatment',
            price=Decimal('400'),
        )
        self.user = User.objects.create_user(username='staff_pay', password='x')
        self.staff = Staff.objects.create(user=self.user, display_name='Pay Staff')
        self.staff.treatments.add(self.treatment)
        for day in range(6):
            StaffAvailability.objects.create(
                staff=self.staff,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(18, 0),
            )
        self.booking_date = date.today() + timedelta(days=2)
        while self.booking_date.weekday() == 6:
            self.booking_date += timedelta(days=1)

    def test_create_appointment_with_payment(self):
        client = Client()
        url = reverse('bookings:create_appointment')
        response = client.post(
            url,
            data={
                'service_ids': [str(self.treatment.pk)],
                'staff_id': str(self.staff.pk),
                'appointment_date': self.booking_date.isoformat(),
                'start_time': '10:00',
                'full_name': 'Test Guest',
                'phone': '0977000001',
                'email': 'guest@test.com',
                'payment_method': 'mobile_money',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        ref = response.json()['booking_reference']
        appt = Appointment.objects.get(booking_reference=ref)
        self.assertEqual(appt.payments.count(), 1)
        self.assertEqual(appt.payments.first().status, PaymentStatus.PENDING)

    def test_pay_later_skips_payment_record(self):
        client = Client()
        url = reverse('bookings:create_appointment')
        response = client.post(
            url,
            data={
                'service_ids': [self.treatment.pk],
                'staff_id': str(self.staff.pk),
                'appointment_date': self.booking_date.isoformat(),
                'start_time': '11:00',
                'full_name': 'Later Guest',
                'phone': '0977000002',
                'payment_method': 'pay_later',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        ref = response.json()['booking_reference']
        appt = Appointment.objects.get(booking_reference=ref)
        self.assertEqual(appt.payments.count(), 0)
