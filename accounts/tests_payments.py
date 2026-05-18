from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import CustomerProfile
from bookings.models import Appointment, AppointmentStatus
from payments.models import Payment, PaymentStatus

User = get_user_model()


class PortalPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pay_user',
            email='pay@example.com',
            password='testpass123',
        )
        CustomerProfile.objects.create(user=self.user, full_name='Pay User', phone='0977000000')
        self.appointment = Appointment.objects.create(
            customer=self.user,
            appointment_date=date(2026, 6, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            total_duration=60,
            total_price=Decimal('300.00'),
            deposit_amount=Decimal('60.00'),
            status=AppointmentStatus.PENDING,
        )
        self.client = Client()
        self.client.login(username='pay_user', password='testpass123')

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('portal_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_loads(self):
        response = self.client.get(reverse('portal_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_payment_list_loads(self):
        response = self.client.get(reverse('payment_list'))
        self.assertEqual(response.status_code, 200)

    def test_upload_payment_creates_pending(self):
        proof = SimpleUploadedFile(
            'proof.jpg',
            b'fake-image-bytes',
            content_type='image/jpeg',
        )
        with patch('notifications.services.send_payment_received', return_value=True):
            with patch('notifications.services.send_staff_payment_received', return_value=True):
                response = self.client.post(
                    reverse('payment_upload', kwargs={
                        'booking_reference': self.appointment.booking_reference,
                    }),
                    data={
                        'amount': '60.00',
                        'payment_method': 'BANK',
                        'payment_reference': 'TX123',
                        'proof_of_payment': proof,
                    },
                )
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(appointment=self.appointment)
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.amount, Decimal('60.00'))
