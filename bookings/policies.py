from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from bookings.models import Appointment, AppointmentStatus

CANCELLATION_NOTICE_HOURS = 24

MODIFIABLE_STATUSES = (
    AppointmentStatus.PENDING,
    AppointmentStatus.CONFIRMED,
)


def appointment_starts_at(appointment: Appointment) -> datetime:
    tz = ZoneInfo(settings.SPA_TIME_ZONE)
    naive = datetime.combine(appointment.appointment_date, appointment.start_time)
    return timezone.make_aware(naive, tz)


def can_modify_appointment(appointment: Appointment) -> bool:
    if appointment.status not in MODIFIABLE_STATUSES:
        return False
    starts = appointment_starts_at(appointment)
    now = timezone.now()
    if starts <= now:
        return False
    notice = timedelta(hours=CANCELLATION_NOTICE_HOURS)
    return (starts - now) >= notice


def can_cancel_appointment(appointment: Appointment) -> bool:
    return can_modify_appointment(appointment)


def can_reschedule_appointment(appointment: Appointment) -> bool:
    return can_modify_appointment(appointment)
