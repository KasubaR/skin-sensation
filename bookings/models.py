import uuid
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, models


class DayOfWeek(models.IntegerChoices):
    MONDAY = 0, 'Monday'
    TUESDAY = 1, 'Tuesday'
    WEDNESDAY = 2, 'Wednesday'
    THURSDAY = 3, 'Thursday'
    FRIDAY = 4, 'Friday'
    SATURDAY = 5, 'Saturday'
    SUNDAY = 6, 'Sunday'


class StaffAvailability(models.Model):
    staff = models.ForeignKey(
        'accounts.Staff',
        on_delete=models.CASCADE,
        related_name='availabilities',
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_off_day = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'staff availability'
        constraints = [
            models.UniqueConstraint(
                fields=['staff', 'day_of_week'],
                name='bookings_staffavail_staff_day_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.staff} — {self.get_day_of_week_display()}'


class AppointmentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    NO_SHOW = 'NO_SHOW', 'No show'


class AppointmentPaymentStatus(models.TextChoices):
    UNPAID = 'UNPAID', 'Unpaid'
    DEPOSIT_PAID = 'DEPOSIT_PAID', 'Deposit paid'
    PAID = 'PAID', 'Paid'
    REFUNDED = 'REFUNDED', 'Refunded'


class Appointment(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='appointments',
    )
    booking_reference = models.CharField(max_length=32, unique=True, db_index=True, blank=True)
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    total_duration = models.PositiveIntegerField(
        default=0,
        help_text='Total duration in minutes.',
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.PENDING,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=AppointmentPaymentStatus.choices,
        default=AppointmentPaymentStatus.UNPAID,
    )
    assigned_staff = models.ForeignKey(
        'accounts.Staff',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_appointments',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-appointment_date', '-start_time']
        indexes = [
            models.Index(fields=['appointment_date', 'start_time']),
            models.Index(fields=['status']),
            models.Index(fields=['customer', 'created_at']),
        ]

    def __str__(self):
        ref = self.booking_reference or '(pending ref)'
        return f'{ref} — {self.appointment_date}'

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = uuid.uuid4().hex[:12]
        for _ in range(5):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError:
                self.booking_reference = uuid.uuid4().hex[:12]
        raise RuntimeError('Could not generate a unique booking reference after 5 attempts.')


class AppointmentService(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='line_items',
    )
    treatment = models.ForeignKey(
        'services.Treatment',
        on_delete=models.PROTECT,
        related_name='appointment_links',
    )
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    duration_snapshot = models.PositiveSmallIntegerField(
        help_text='Duration in minutes at time of booking.',
    )

    class Meta:
        verbose_name = 'appointment service'
        verbose_name_plural = 'appointment services'

    def __str__(self):
        return f'{self.appointment.booking_reference} — {self.treatment}'
