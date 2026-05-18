from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Union

from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import Staff
from bookings.models import Appointment, AppointmentStatus, DayOfWeek, StaffAvailability
from bookings.pricing import (
    BUFFER_MINUTES,
    SLOT_INTERVAL_MINUTES,
    calculate_appointment_minutes,
    calculate_total_duration,
)
from services.models import Treatment

DEFAULT_OPEN = time(9, 0)
DEFAULT_CLOSE = time(18, 0)


def _is_any_staff(staff_id) -> bool:
    return staff_id is None or str(staff_id).lower() == 'any'

ACTIVE_STATUSES = (
    AppointmentStatus.PENDING,
    AppointmentStatus.CONFIRMED,
)


def intervals_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and start_b < end_a


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(minutes: int) -> time:
    if minutes >= 1440:
        raise ValueError(f'Computed time {minutes}m exceeds midnight.')
    return time(minutes // 60, minutes % 60)


def _combine(date_value: date, t: time) -> datetime:
    return datetime.combine(date_value, t)


def get_treatments_by_ids(service_ids: List[int]) -> List[Treatment]:
    """service_ids are treatment primary keys (legacy param name)."""
    treatments = list(
        Treatment.objects.filter(pk__in=service_ids, is_active=True).order_by('pk')
    )
    found_ids = {t.pk for t in treatments}
    if len(found_ids) != len(set(service_ids)):
        missing = set(service_ids) - found_ids
        raise ValueError(f'Invalid or inactive treatment ids: {sorted(missing)}')
    return treatments


get_services_by_ids = get_treatments_by_ids


def get_eligible_staff(
    service_ids: List[int],
    staff_id: Union[int, str, None] = None,
) -> List[Staff]:
    qs = Staff.objects.filter(is_available=True).annotate(
        treatment_count=Count('treatments'),
    )

    if service_ids:
        qs = qs.filter(
            Q(treatment_count=0) | Q(treatments__pk__in=service_ids),
        ).distinct()

    qs = qs.filter(
        availabilities__is_off_day=False,
    ).distinct()

    if not _is_any_staff(staff_id):
        qs = qs.filter(pk=int(staff_id))
    return list(qs)


def get_staff_working_window(staff: Staff, appointment_date: date) -> Optional[Tuple[time, time]]:
    weekday = appointment_date.weekday()
    availability = StaffAvailability.objects.filter(
        staff=staff,
        day_of_week=weekday,
        is_off_day=False,
    ).first()
    if availability:
        return availability.start_time, availability.end_time
    if StaffAvailability.objects.filter(staff=staff).exists():
        return None
    return DEFAULT_OPEN, DEFAULT_CLOSE


def get_staff_appointments(
    staff: Staff,
    appointment_date: date,
    exclude_appointment_id: Optional[int] = None,
):
    qs = Appointment.objects.filter(
        assigned_staff=staff,
        appointment_date=appointment_date,
        status__in=ACTIVE_STATUSES,
    )
    if exclude_appointment_id is not None:
        qs = qs.exclude(pk=exclude_appointment_id)
    return qs.order_by('start_time')


def _slot_fits_window(
    slot_start: time,
    appointment_minutes: int,
    window_start: time,
    window_end: time,
) -> bool:
    start_m = _time_to_minutes(slot_start)
    end_m = start_m + appointment_minutes
    return start_m >= _time_to_minutes(window_start) and end_m <= _time_to_minutes(window_end)


def _slot_conflicts_appointments(
    slot_start: time,
    appointment_minutes: int,
    appointments,
) -> bool:
    slot_end = _minutes_to_time(_time_to_minutes(slot_start) + appointment_minutes)
    for appt in appointments:
        if intervals_overlap(slot_start, slot_end, appt.start_time, appt.end_time):
            return True
    return False


def _generate_slot_starts(window_start: time, window_end: time) -> list[time]:
    starts = []
    cursor = _time_to_minutes(window_start)
    end_limit = _time_to_minutes(window_end)
    while cursor < end_limit:
        starts.append(_minutes_to_time(cursor))
        cursor += SLOT_INTERVAL_MINUTES
    return starts


def _compute_staff_slots(
    staff: Staff,
    window: Optional[Tuple[time, time]],
    appointments: list,
    appointment_date: date,
    appointment_minutes: int,
    now,
) -> list[dict]:
    if not window:
        return []
    window_start, window_end = window
    is_today = appointment_date == now.date()
    slots = []
    for slot_start in _generate_slot_starts(window_start, window_end):
        if not _slot_fits_window(slot_start, appointment_minutes, window_start, window_end):
            continue
        if _slot_conflicts_appointments(slot_start, appointment_minutes, appointments):
            continue
        if is_today:
            slot_dt = _combine(appointment_date, slot_start)
            if timezone.make_aware(slot_dt) <= now:
                continue
        slot_end = _minutes_to_time(_time_to_minutes(slot_start) + appointment_minutes)
        slots.append({
            'start': slot_start.strftime('%H:%M'),
            'end': slot_end.strftime('%H:%M'),
            'staff_id': staff.pk,
            'staff_name': staff.display_name,
        })
    return slots


def get_staff_slots_for_date(
    staff: Staff,
    appointment_date: date,
    services: list[Treatment],
) -> list[dict]:
    window = get_staff_working_window(staff, appointment_date)
    appointment_minutes = calculate_appointment_minutes(services)
    appointments = list(get_staff_appointments(staff, appointment_date))
    return _compute_staff_slots(staff, window, appointments, appointment_date, appointment_minutes, timezone.localtime())


def get_available_slots(
    *,
    appointment_date: date,
    service_ids: list[int],
    staff_id: Union[int, str, None] = None,
    exclude_appointment_id: Optional[int] = None,
) -> dict:
    services = get_services_by_ids(service_ids)
    appointment_minutes = calculate_appointment_minutes(services)
    staff_members = get_eligible_staff(service_ids, staff_id)

    weekday = appointment_date.weekday()

    # Pre-fetch working windows for all staff in one query.
    avail_map = {
        a.staff_id: a
        for a in StaffAvailability.objects.filter(
            staff__in=staff_members,
            day_of_week=weekday,
            is_off_day=False,
        )
    }
    # Track which staff have *any* availability rows (needed to distinguish
    # "no row for today → use defaults" from "has rows but not today → off").
    has_any_avail_ids = set(
        StaffAvailability.objects.filter(staff__in=staff_members)
        .values_list('staff_id', flat=True)
        .distinct()
    )

    # Pre-fetch all appointments for this date across all staff in one query.
    appt_map: Dict[int, list] = defaultdict(list)
    appt_qs = Appointment.objects.filter(
        assigned_staff__in=staff_members,
        appointment_date=appointment_date,
        status__in=ACTIVE_STATUSES,
    )
    if exclude_appointment_id is not None:
        appt_qs = appt_qs.exclude(pk=exclude_appointment_id)
    for appt in appt_qs.order_by('start_time'):
        appt_map[appt.assigned_staff_id].append(appt)

    now = timezone.localtime()
    slot_map: Dict[str, dict] = {}
    for staff in staff_members:
        avail = avail_map.get(staff.pk)
        if avail:
            window = (avail.start_time, avail.end_time)
        elif staff.pk in has_any_avail_ids:
            window = None  # has rows but not working today
        else:
            window = (DEFAULT_OPEN, DEFAULT_CLOSE)

        for slot in _compute_staff_slots(
            staff, window, appt_map[staff.pk], appointment_date, appointment_minutes, now
        ):
            key = slot['start']
            if key not in slot_map:
                slot_map[key] = slot
            elif _is_any_staff(staff_id):
                existing = slot_map[key]
                if staff.pk not in existing.get('staff_ids', [existing['staff_id']]):
                    ids = existing.get('staff_ids', [existing['staff_id']])
                    ids.append(staff.pk)
                    existing['staff_ids'] = ids

    slots = sorted(slot_map.values(), key=lambda s: s['start'])
    return {
        'slots': slots,
        'appointment_minutes': appointment_minutes,
        'total_duration': calculate_total_duration(services),
        'buffer_minutes': BUFFER_MINUTES if services else 0,
    }


def slot_is_available(
    *,
    staff: Staff,
    appointment_date: date,
    start_time: time,
    services: list[Treatment],
    exclude_appointment_id: Optional[int] = None,
) -> bool:
    appointment_minutes = calculate_appointment_minutes(services)
    window = get_staff_working_window(staff, appointment_date)
    if not window:
        return False
    window_start, window_end = window
    if not _slot_fits_window(start_time, appointment_minutes, window_start, window_end):
        return False
    appointments = list(
        get_staff_appointments(staff, appointment_date, exclude_appointment_id=exclude_appointment_id)
    )
    if _slot_conflicts_appointments(start_time, appointment_minutes, appointments):
        return False
    now = timezone.localtime()
    if appointment_date == now.date():
        slot_dt = _combine(appointment_date, start_time)
        if timezone.make_aware(slot_dt) <= now:
            return False
    return True


def resolve_staff_for_slot(
    *,
    service_ids: list[int],
    appointment_date: date,
    start_time: time,
    staff_id: Union[int, str, None],
    services: Optional[List[Treatment]] = None,
    exclude_appointment_id: Optional[int] = None,
) -> Optional[Staff]:
    if services is None:
        services = get_services_by_ids(service_ids)

    if not _is_any_staff(staff_id):
        staff = Staff.objects.filter(pk=int(staff_id), is_available=True).first()
        if staff and staff.can_perform_services(service_ids) and slot_is_available(
            staff=staff,
            appointment_date=appointment_date,
            start_time=start_time,
            services=services,
            exclude_appointment_id=exclude_appointment_id,
        ):
            return staff
        return None

    for staff in get_eligible_staff(service_ids, staff_id='any'):
        if slot_is_available(
            staff=staff,
            appointment_date=appointment_date,
            start_time=start_time,
            services=services,
            exclude_appointment_id=exclude_appointment_id,
        ):
            return staff
    return None


def compute_end_time(start_time: time, services: list[Treatment]) -> time:
    minutes = calculate_appointment_minutes(services)
    return _minutes_to_time(_time_to_minutes(start_time) + minutes)
