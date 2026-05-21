from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q

from bookings.models import Appointment, AppointmentStatus
from services.models import Service
from testimonials.models import Testimonial
from testimonials.selectors import FEATURED_LIMIT, approved_for_public_list, featured_for_homepage
from testimonials.validators import validate_review_eligibility


def get_reviewable_services(user):
    completed_service_ids = (
        Appointment.objects.filter(
            customer=user,
            status=AppointmentStatus.COMPLETED,
            line_items__treatment__service__isnull=False,
        )
        .values_list('line_items__treatment__service_id', flat=True)
        .distinct()
    )
    reviewed_service_ids = Testimonial.objects.filter(
        customer=user,
        service__isnull=False,
    ).values_list('service_id', flat=True)

    return (
        Service.objects.filter(
            is_active=True,
            pk__in=completed_service_ids,
        )
        .exclude(pk__in=reviewed_service_ids)
        .order_by('sort_order', 'name')
    )


def get_featured_testimonials(limit: int = FEATURED_LIMIT):
    return featured_for_homepage(limit=limit)


def get_approved_testimonials(**filters):
    service_slug = filters.get('service_slug')
    return approved_for_public_list(service_slug=service_slug)


def calculate_average_rating(*, service=None):
    qs = Testimonial.objects.filter(status=Testimonial.Status.APPROVED)
    if service is not None:
        qs = qs.filter(service=service)
    return qs.aggregate(avg=Avg('rating'))['avg']


@transaction.atomic
def submit_review(user, *, service, rating, title='', review=''):
    validate_review_eligibility(user, service)
    rating = int(rating)
    if rating < 1 or rating > 5:
        raise ValidationError('Rating must be between 1 and 5 stars.')
    review_text = (review or '').strip()
    if not review_text:
        raise ValidationError('Please write your review.')

    try:
        testimonial = Testimonial.objects.create(
            customer=user,
            service=service,
            rating=rating,
            title=(title or '').strip(),
            review=review_text,
            status=Testimonial.Status.PENDING,
        )
    except IntegrityError:
        raise ValidationError('You have already submitted a review for this service.') from None

    from notifications.services import send_review_submitted_notification

    transaction.on_commit(lambda: send_review_submitted_notification(testimonial))
    return testimonial


@transaction.atomic
def approve_review(testimonial: Testimonial) -> Testimonial:
    was_approved = testimonial.status == Testimonial.Status.APPROVED
    testimonial.status = Testimonial.Status.APPROVED
    testimonial.save(update_fields=['status', 'updated_at'])

    if not was_approved:
        from notifications.services import send_review_approved_email

        transaction.on_commit(lambda: send_review_approved_email(testimonial))
    return testimonial


@transaction.atomic
def reject_review(testimonial: Testimonial) -> Testimonial:
    testimonial.status = Testimonial.Status.REJECTED
    testimonial.is_featured = False
    testimonial.save(update_fields=['status', 'is_featured', 'updated_at'])
    return testimonial


@transaction.atomic
def feature_review(testimonial: Testimonial, *, featured: bool = True) -> Testimonial:
    testimonial = Testimonial.objects.select_for_update().get(pk=testimonial.pk)
    if testimonial.status != Testimonial.Status.APPROVED:
        raise ValidationError('Only approved reviews can be featured.')
    if featured and not testimonial.is_featured:
        count = Testimonial.objects.select_for_update().filter(
            status=Testimonial.Status.APPROVED,
            is_featured=True,
        ).count()
        if count >= FEATURED_LIMIT:
            raise ValidationError(
                f'At most {FEATURED_LIMIT} reviews can be featured on the homepage.'
            )
    testimonial.is_featured = featured
    testimonial.save(update_fields=['is_featured', 'updated_at'])
    return testimonial


def delete_review(testimonial: Testimonial) -> None:
    testimonial.delete()
