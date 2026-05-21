from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from communications.models import BusinessInformation, ContactMessage

User = get_user_model()


class BusinessInformationTests(TestCase):
    def test_singleton_load(self):
        business = BusinessInformation.load()
        self.assertEqual(business.pk, 1)
        self.assertIn('Kabulonga', business.address)

    def test_tel_and_whatsapp_hrefs(self):
        business = BusinessInformation.load()
        self.assertTrue(business.tel_href.startswith('tel:+'))
        self.assertIn('wa.me', business.whatsapp_href)

    def test_save_forces_pk_one(self):
        business = BusinessInformation.load()
        business.phone_number = '+260 999 000 111'
        business.save()
        self.assertEqual(BusinessInformation.objects.count(), 1)
        self.assertEqual(BusinessInformation.load().phone_number, '+260 999 000 111')


class ContactFormTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _valid_payload(self):
        return {
            'full_name': 'Jane Doe',
            'email': 'jane@example.com',
            'phone_number': '+260971234567',
            'subject': 'general',
            'message': 'Hello, I have a question.',
            'website': '',
        }

    @patch('communications.views.send_contact_notification')
    def test_contact_form_creates_message_and_redirects(self, mock_notify):
        response = self.client.post(reverse('contact'), self._valid_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('contact_success'))
        self.assertEqual(ContactMessage.objects.count(), 1)
        mock_notify.assert_called_once()

    @patch('communications.views.send_contact_notification')
    def test_honeypot_rejects_submission(self, mock_notify):
        payload = self._valid_payload()
        payload['website'] = 'spam'
        response = self.client.post(reverse('contact'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        mock_notify.assert_not_called()


class StaffDashboardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff1',
            email='staff@example.com',
            password='testpass123',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='cust1',
            email='cust@example.com',
            password='testpass123',
        )
        self.message = ContactMessage.objects.create(
            full_name='Test User',
            email='test@example.com',
            phone_number='+260971234567',
            subject='General enquiry',
            message='Test body',
        )

    def test_staff_can_list_messages(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('dashboard:contact_message_list'))
        self.assertEqual(response.status_code, 200)

    def test_non_staff_denied(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('dashboard:contact_message_list'))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_business_settings(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('dashboard:business_settings'))
        self.assertEqual(response.status_code, 200)
