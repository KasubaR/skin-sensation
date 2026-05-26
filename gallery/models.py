from django.db import models

from gallery.validators import validate_gallery_image


class GalleryImage(models.Model):
    class Category(models.TextChoices):
        INTERIOR = 'interior', 'Spa Interior'
        FACIALS = 'facials', 'Facials'
        MASSAGE = 'massage', 'Massage'
        BODY_NAILS = 'body-nails', 'Body & Nails'
        TEAM = 'team', 'Team & Atmosphere'

    class Layout(models.TextChoices):
        DEFAULT = 'default', 'Default'
        WIDE = 'wide', 'Wide'
        TALL = 'tall', 'Tall'

    image = models.ImageField(upload_to='gallery/')
    category = models.CharField(max_length=20, choices=Category.choices)
    caption = models.CharField(max_length=255)
    alt_text = models.CharField(max_length=255)
    layout = models.CharField(
        max_length=10,
        choices=Layout.choices,
        default=Layout.DEFAULT,
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'category', 'sort_order']),
        ]

    def __str__(self):
        return self.caption

    def clean(self):
        super().clean()
        if self.image:
            validate_gallery_image(self.image)

    @property
    def category_label(self) -> str:
        return self.Category(self.category).label

    @property
    def grid_modifier_class(self) -> str:
        if self.layout == self.Layout.WIDE:
            return 'gallery-item--wide'
        if self.layout == self.Layout.TALL:
            return 'gallery-item--tall'
        return ''

    @property
    def lightbox_url(self) -> str:
        return self.image.url if self.image else ''
