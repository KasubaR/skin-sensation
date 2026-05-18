from django.conf import settings
from django.db import models


class Staff(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile',
    )
    display_name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    image = models.ImageField(upload_to='staff/', blank=True)
    is_available = models.BooleanField(default=True)
    treatments = models.ManyToManyField(
        'services.Treatment',
        blank=True,
        related_name='staff_members',
        help_text='Leave empty to allow all treatments.',
    )

    class Meta:
        verbose_name_plural = 'staff'

    def __str__(self):
        return self.display_name

    def can_perform_services(self, service_ids: list[int]) -> bool:
        """service_ids are treatment primary keys (legacy param name)."""
        if not service_ids:
            return True
        if not self.treatments.exists():
            return True
        return self.treatments.filter(pk__in=service_ids).exists()


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_profile',
    )
    phone = models.CharField(max_length=32, blank=True)
    full_name = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'customer profile'
        verbose_name_plural = 'customer profiles'

    @property
    def phone_display(self):
        p = self.phone
        if len(p) == 10 and p.startswith('0'):
            return f'{p[:4]} {p[4:7]} {p[7:]}'
        return p

    def __str__(self):
        return self.full_name or self.user.get_username()
