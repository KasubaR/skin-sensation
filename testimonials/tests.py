from datetime import date, time
from decimal import Decimal
from itertools import count
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from bookings.models import Appointment, AppointmentService, AppointmentStatus
from services.models import Service, Treatment
from testimonials.models import Testimonial
from testimonials.selectors import FEATURED_LIMIT
from testimonials.services import approve_review, feature_review, submit_review

User = get_user_model()

_user_counter = count(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email=None):
    if email is None:
        email = f'user{next(_user_counter)}@example.com'
    return User.objects.create_user(username=email, email=email, password='pw')


def _make_service(slug='waxing'):
    service, _ = Service.objects.get_or_create(
        slug=slug,
        defaults={'name': slug.title(), 'is_active': True},
    )
    return service


def _make_treatment(service):
    treatment, _ = Treatment.objects.get_or_create(
        slug=f'{service.slug}-basic',
        defaults={
            'service': service,
            'name': 'Basic',
            'duration_minutes': 30,
            'price': Decimal('200.00'),
            'is_active': True,
        },
    )
    return treatment


def _make_appointment(user, treatment, *, status=AppointmentStatus.COMPLETED):
    appt = Appointment.objects.create(
        customer=user,
        appointment_date=date(2025, 1, 1),
        start_time=time(10, 0),
        end_time=time(10, 30),
        status=status,
    )
    AppointmentService.objects.create(
        appointment=appt,
        treatment=treatment,
        price_snapshot=treatment.price,
        duration_snapshot=treatment.duration_minutes,
    )
    return appt


def _make_approved_testimonial(*, featured=False, service=None, user=None):
    if user is None:
        user = _make_user()
    return Testimonial.objects.create(
        customer=user,
        service=service,
        rating=5,
        review='Great.',
        status=Testimonial.Status.APPROVED,
        is_featured=featured,
    )


# ---------------------------------------------------------------------------
# submit_review
# ---------------------------------------------------------------------------

class SubmitReviewEligibilityTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.service = _make_service()
        self.treatment = _make_treatment(self.service)

    def test_blocks_user_without_completed_appointment(self):
        with self.assertRaises(ValidationError):
            submit_review(self.user, service=self.service, rating=5, review='Loved it.')

    def test_blocks_user_with_only_pending_appointment(self):
        _make_appointment(self.user, self.treatment, status=AppointmentStatus.PENDING)
        with self.assertRaises(ValidationError):
            submit_review(self.user, service=self.service, rating=5, review='Loved it.')

    @patch('notifications.services.send_review_submitted_notification')
    def test_allows_user_with_completed_appointment(self, _mock):
        _make_appointment(self.user, self.treatment)
        testimonial = submit_review(
            self.user, service=self.service, rating=4, review='Very good.'
        )
        self.assertEqual(testimonial.status, Testimonial.Status.PENDING)
        self.assertEqual(testimonial.customer, self.user)

    @patch('notifications.services.send_review_submitted_notification')
    def test_blocks_duplicate_service_review(self, _mock):
        _make_appointment(self.user, self.treatment)
        submit_review(self.user, service=self.service, rating=4, review='First review.')
        with self.assertRaises(ValidationError):
            submit_review(self.user, service=self.service, rating=5, review='Second review.')

    @patch('notifications.services.send_review_submitted_notification')
    def test_notification_scheduled_on_commit(self, mock_notify):
        _make_appointment(self.user, self.treatment)
        with self.captureOnCommitCallbacks(execute=True):
            submit_review(self.user, service=self.service, rating=5, review='Amazing.')
        mock_notify.assert_called_once()


# ---------------------------------------------------------------------------
# approve_review
# ---------------------------------------------------------------------------

class ApproveReviewNotificationTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.service = _make_service()
        self.testimonial = Testimonial.objects.create(
            customer=self.user,
            service=self.service,
            rating=5,
            review='Good.',
            status=Testimonial.Status.PENDING,
        )

    @patch('notifications.services.send_review_approved_email')
    def test_sends_notification_on_first_approval(self, mock_email):
        with self.captureOnCommitCallbacks(execute=True):
            approve_review(self.testimonial)
        mock_email.assert_called_once()

    @patch('notifications.services.send_review_approved_email')
    def test_no_notification_on_re_approval(self, mock_email):
        self.testimonial.status = Testimonial.Status.APPROVED
        self.testimonial.save()
        with self.captureOnCommitCallbacks(execute=True):
            approve_review(self.testimonial)
        mock_email.assert_not_called()

    def test_sets_status_to_approved(self):
        approve_review(self.testimonial)
        self.testimonial.refresh_from_db()
        self.assertEqual(self.testimonial.status, Testimonial.Status.APPROVED)


# ---------------------------------------------------------------------------
# feature_review
# ---------------------------------------------------------------------------

class FeatureReviewLimitTests(TestCase):
    def setUp(self):
        self.service = _make_service()
        # Fill featured slots to the limit
        for i in range(FEATURED_LIMIT):
            _make_approved_testimonial(featured=True, service=self.service)

    def test_feature_beyond_limit_raises(self):
        extra = _make_approved_testimonial(featured=False, service=self.service)
        with self.assertRaises(ValidationError):
            feature_review(extra, featured=True)

    def test_feature_within_limit_succeeds(self):
        # Unfeature one, then featuring another should work
        Testimonial.objects.filter(is_featured=True).first().delete()
        extra = _make_approved_testimonial(featured=False, service=self.service)
        result = feature_review(extra, featured=True)
        self.assertTrue(result.is_featured)

    def test_unfeature_does_not_check_limit(self):
        featured = Testimonial.objects.filter(is_featured=True).first()
        result = feature_review(featured, featured=False)
        self.assertFalse(result.is_featured)

    def test_re_featuring_already_featured_does_not_raise(self):
        featured = Testimonial.objects.filter(is_featured=True).first()
        # Already featured — limit check is skipped (not incrementing)
        result = feature_review(featured, featured=True)
        self.assertTrue(result.is_featured)

    def test_feature_pending_review_raises(self):
        user = _make_user()
        pending = Testimonial.objects.create(
            customer=user,
            service=self.service,
            rating=3,
            review='Meh.',
            status=Testimonial.Status.PENDING,
        )
        with self.assertRaises(ValidationError):
            feature_review(pending, featured=True)
