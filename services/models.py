from django.db import models


class Service(models.Model):
    """Top-level menu group (e.g. Nail Treatment, Massage Therapy)."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='services/', blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @property
    def card_image_url(self) -> str:
        from services.constants import service_card_image_url
        return service_card_image_url(self.slug)


class Treatment(models.Model):
    """Bookable treatment within a service group."""

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='treatments',
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    benefits = models.TextField(
        blank=True,
        help_text='One benefit per line, shown on the treatment detail page.',
    )
    duration_minutes = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_from = models.BooleanField(
        default=False,
        help_text='Show "From" before the price (e.g. variable or tiered pricing).',
    )
    price_label = models.CharField(
        max_length=64,
        blank=True,
        help_text='Optional override, e.g. K500–K1,000',
    )
    image = models.ImageField(upload_to='services/', blank=True)
    subsection = models.CharField(
        max_length=64,
        blank=True,
        help_text='Non-empty groups treatments under a subheading (e.g. Add-On Treatments).',
    )
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['service', 'subsection', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['service', 'is_active']),
            models.Index(fields=['name']),
            models.Index(
                fields=['subsection', 'sort_order', 'name'],
                name='svc_tr_subsection_sort_idx',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def benefits_list(self):
        return [line.strip() for line in self.benefits.splitlines() if line.strip()]

    def display_price(self):
        if self.price_label:
            return self.price_label
        amount = int(self.price) if self.price == self.price.to_integral_value() else self.price
        return f'K{amount}'
