import re
from urllib.parse import quote

from django.db import models

SUBJECT_CHOICES = [
    ('general', 'General enquiry'),
    ('booking', 'Booking help'),
    ('group', 'Group / event booking'),
    ('services', 'Services question'),
    ('feedback', 'Feedback'),
    ('other', 'Other'),
]


def _digits_only(value: str) -> str:
    return re.sub(r'\D', '', value or '')


class BusinessInformation(models.Model):
    """Singleton row (pk=1) for spa contact details shown site-wide."""

    business_name = models.CharField(max_length=255, default='Skin Sensation Spa')

    phone_number = models.CharField(
        max_length=20,
        help_text='Display format, e.g. +260 973 407 110',
    )
    whatsapp_number = models.CharField(
        max_length=20,
        help_text='Digits only for wa.me links, e.g. 260973407110',
    )

    email = models.EmailField()

    address = models.TextField()

    google_maps_embed_url = models.TextField(
        blank=True,
        help_text='Full iframe src URL from Google Maps → Share → Embed',
    )

    opening_hours = models.JSONField(default=dict, blank=True)

    whatsapp_prefill_message = models.TextField(
        blank=True,
        default='Hello Skin Sensation Spa, I would like to inquire about your services.',
    )

    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Business information'
        verbose_name_plural = 'Business information'

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.delete('business_info')

    def delete(self, *args, **kwargs):
        raise TypeError("BusinessInformation is a singleton and cannot be deleted.")

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'business_name': 'Skin Sensation Spa',
                'phone_number': '+260 973 407 110',
                'whatsapp_number': '260973407110',
                'email': 'info@skinsensationspa.com',
                'address': 'Kabulonga, Kudu Road, Springbok Close, Lusaka',
                'opening_hours': {
                    'monday_friday': '8:00 am – 6:00 pm',
                    'saturday': '9:00 am – 5:00 pm',
                    'sunday': '10:00 am – 4:00 pm',
                },
                'instagram_url': 'https://www.instagram.com/skinsensationbeautyspa',
            },
        )
        return obj

    @property
    def tel_href(self) -> str:
        digits = _digits_only(self.phone_number)
        return f'tel:+{digits}' if digits else ''

    @property
    def whatsapp_href(self) -> str:
        digits = _digits_only(self.whatsapp_number)
        if not digits:
            return ''
        url = f'https://wa.me/{digits}'
        if self.whatsapp_prefill_message.strip():
            url = f'{url}?text={quote(self.whatsapp_prefill_message.strip())}'
        return url

    @property
    def maps_directions_href(self) -> str:
        if self.address.strip():
            return f'https://maps.google.com/?q={quote(self.address.strip())}'
        return 'https://maps.google.com/'

    @property
    def maps_embed_src(self) -> str:
        if self.google_maps_embed_url.strip():
            return self.google_maps_embed_url.strip()
        return (
            'https://www.google.com/maps?q='
            + quote(self.address.strip())
            + '&output=embed'
        )


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        READ = 'read', 'Read'
        REPLIED = 'replied', 'Replied'

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        return f'{self.full_name} — {self.subject}'
