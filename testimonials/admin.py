from django.contrib import admin
from django.db import transaction

from notifications.services import send_review_approved_email
from testimonials.models import Testimonial
from testimonials.services import feature_review, reject_review


@admin.action(description='Approve selected reviews')
def approve_testimonials(modeladmin, request, queryset):
    to_notify = list(queryset.filter(status=Testimonial.Status.PENDING))
    queryset.update(status=Testimonial.Status.APPROVED)
    for testimonial in to_notify:
        testimonial.status = Testimonial.Status.APPROVED
        transaction.on_commit(lambda t=testimonial: send_review_approved_email(t))


@admin.action(description='Reject selected reviews')
def reject_testimonials(modeladmin, request, queryset):
    queryset.update(status=Testimonial.Status.REJECTED, is_featured=False)


@admin.action(description='Feature selected reviews (must be approved)')
def feature_testimonials(modeladmin, request, queryset):
    for testimonial in queryset.filter(status=Testimonial.Status.APPROVED):
        feature_review(testimonial, featured=True)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'service',
        'rating',
        'status',
        'is_featured',
        'created_at',
    )
    list_filter = ('status', 'is_featured', 'rating', 'created_at')
    search_fields = (
        'review',
        'title',
        'customer__email',
        'customer__first_name',
        'customer__last_name',
    )
    raw_id_fields = ('customer', 'service')
    readonly_fields = ('created_at', 'updated_at')
    actions = [approve_testimonials, reject_testimonials, feature_testimonials]
