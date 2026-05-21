from datetime import date, time
from typing import Optional, Union

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from bookings.models import Appointment, AppointmentStatus
from bookings.validators import validate_cancellation_window
from bookings.pricing import calculate_appointment_window
from bookings.scheduling import (
    _is_any_staff,
    compute_end_time,
    get_services_by_ids,
    resolve_staff_for_slot,
    slot_is_available,
)
from accounts.models import Staff
from notifications.services import notify_appointment_cancelled, notify_appointment_rescheduled

User = get_user_model()


class PortalError(Exception):
    """Customer portal action could not be completed."""


def get_customer_appointment(user: User, booking_reference: str) -> Appointment:
    return get_object_or_404(
        Appointment.objects.select_related('assigned_staff', 'customer')
        .prefetch_related('line_items__treatment__service', 'payments'),
        customer=user,
        booking_reference=booking_reference,
    )


def cancel_appointment(appointment: Appointment) -> Appointment:
    try:
        validate_cancellation_window(appointment)
    except ValidationError as exc:
        raise PortalError(exc.messages[0] if exc.messages else str(exc)) from exc

    with transaction.atomic():
        appointment.status = AppointmentStatus.CANCELLED
        appointment.save(update_fields=['status'])
        transaction.on_commit(lambda: notify_appointment_cancelled(appointment))
    return appointment


def reschedule_appointment(
    appointment: Appointment,
    new_date: date,
    new_start_time: time,
    staff_id: Union[int, str, None] = None,
    user=None,
    *,
    staff_override: bool = False,
) -> Appointment:
    if user is not None and appointment.customer_id != user.pk:
        raise PortalError('You do not have permission to reschedule this appointment.')
    if not staff_override:
        try:
            validate_cancellation_window(appointment)
        except ValidationError as exc:
            raise PortalError(exc.messages[0] if exc.messages else str(exc)) from exc
    elif appointment.status not in (
        AppointmentStatus.PENDING,
        AppointmentStatus.CONFIRMED,
    ):
        raise PortalError('Only pending or confirmed appointments can be rescheduled.')

    if new_date < timezone.localdate():
        raise PortalError('Appointment date must be today or in the future.')

    service_ids = list(appointment.line_items.values_list('treatment_id', flat=True))
    if not service_ids:
        raise PortalError('This appointment has no services and cannot be rescheduled.')

    services = get_services_by_ids(service_ids)

    if staff_id is None:
        staff_id = appointment.assigned_staff_id if appointment.assigned_staff_id else 'any'

    with transaction.atomic():
        Appointment.objects.select_for_update().get(pk=appointment.pk)

        if not _is_any_staff(staff_id):
            staff = Staff.objects.filter(pk=int(staff_id), is_available=True).first()
            if not staff or not staff.can_perform_services(service_ids):
                raise PortalError('The selected therapist is not available for these services.')
            if not slot_is_available(
                staff=staff,
                appointment_date=new_date,
                start_time=new_start_time,
                services=services,
                exclude_appointment_id=appointment.pk,
            ):
                raise PortalError('That time slot is no longer available. Please choose another.')
        else:
            staff = resolve_staff_for_slot(
                service_ids=service_ids,
                appointment_date=new_date,
                start_time=new_start_time,
                staff_id='any',
                services=services,
                exclude_appointment_id=appointment.pk,
            )
            if not staff:
                raise PortalError('That time slot is no longer available. Please choose another.')

        window = calculate_appointment_window(services)
        appointment.appointment_date = new_date
        appointment.start_time = new_start_time
        appointment.end_time = compute_end_time(new_start_time, services)
        appointment.total_duration = window['total_duration']
        appointment.assigned_staff = staff
        appointment.save(
            update_fields=[
                'appointment_date',
                'start_time',
                'end_time',
                'total_duration',
                'assigned_staff',
            ]
        )

        transaction.on_commit(lambda: notify_appointment_rescheduled(appointment))
    return appointment
