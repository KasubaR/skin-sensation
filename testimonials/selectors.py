from django.db.models import Avg, Count, Q

from services.models import Service
from testimonials.models import Testimonial

FEATURED_LIMIT = 8


def featured_for_homepage(limit: int = FEATURED_LIMIT):
    return (
        Testimonial.objects.filter(
            status=Testimonial.Status.APPROVED,
            is_featured=True,
        )
        .select_related('customer', 'customer__customer_profile', 'service')
        .order_by('-rating', '-created_at')[:limit]
    )


def approved_for_public_list(*, service_slug: str | None = None):
    qs = (
        Testimonial.objects.filter(status=Testimonial.Status.APPROVED)
        .select_related('customer', 'customer__customer_profile', 'service')
        .order_by('-created_at')
    )
    if service_slug:
        qs = qs.filter(service__slug=service_slug)
    return qs


def pending_for_dashboard():
    return (
        Testimonial.objects.filter(status=Testimonial.Status.PENDING)
        .select_related('customer', 'customer__customer_profile', 'service')
        .order_by('-created_at')
    )


def service_rating_summary():
    return (
        Service.objects.filter(is_active=True)
        .annotate(
            review_count=Count(
                'testimonials',
                filter=Q(testimonials__status=Testimonial.Status.APPROVED),
            ),
            average_rating=Avg(
                'testimonials__rating',
                filter=Q(testimonials__status=Testimonial.Status.APPROVED),
            ),
        )
        .filter(review_count__gt=0)
    )
