from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Testimonial(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='testimonials',
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='testimonials',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField(max_length=255, blank=True)
    review = models.TextField()
    is_featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'service'],
                condition=models.Q(service__isnull=False),
                name='unique_testimonial_per_customer_service',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['status', 'is_featured', '-rating']),
        ]

    def __str__(self):
        return f'{self.customer_id} — {self.rating}★ ({self.status})'

    @property
    def display_author_name(self) -> str:
        profile = getattr(self.customer, 'customer_profile', None)
        if profile and profile.full_name:
            full = profile.full_name.strip()
        else:
            full = (self.customer.get_full_name() or '').strip()
        if not full:
            return 'Guest'
        parts = full.split()
        if len(parts) == 1:
            return f'{parts[0][0].upper()}.'
        return f'{parts[0]} {parts[-1][0].upper()}.'

    @property
    def display_quote(self) -> str:
        if self.title:
            return self.title
        text = self.review.strip()
        if len(text) <= 120:
            return text
        return f'{text[:117]}…'
