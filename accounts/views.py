from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from bookings.models import Appointment, AppointmentStatus
from bookings.portal import (
    PortalError,
    cancel_appointment,
    get_customer_appointment,
    reschedule_appointment,
)
from bookings.policies import can_cancel_appointment, can_reschedule_appointment
from notifications.context import appointment_email_context
from payments.models import PaymentStatus


def _parse_appointment_date(value: str):
    return datetime.strptime(value, '%Y-%m-%d').date()


def _parse_start_time(value: str):
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError('Invalid time format.')


def _portal_context(appointment: Appointment) -> dict:
    ctx = appointment_email_context(appointment)
    ctx.update({
        'can_cancel': can_cancel_appointment(appointment),
        'can_reschedule': can_reschedule_appointment(appointment),
        'line_items': list(appointment.line_items.select_related('treatment')),
        'payment_status_display': appointment.get_payment_status_display(),
        'status_display': appointment.get_status_display(),
    })
    return ctx


def _split_appointments(queryset):
    today = timezone.localdate()
    terminal = (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    )
    upcoming = queryset.filter(
        status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
        appointment_date__gte=today,
    )
    history = queryset.filter(
        Q(appointment_date__lt=today) | Q(status__in=terminal),
    )
    return upcoming, history


@login_required
@require_GET
def appointment_list(request):
    qs = (
        request.user.appointments.select_related('assigned_staff')
        .prefetch_related('line_items__treatment')
    )
    upcoming, history = _split_appointments(qs)
    return render(
        request,
        'accounts/portal/appointment_list.html',
        {
            'upcoming': upcoming,
            'history': history,
        },
    )


@login_required
@require_GET
def appointment_detail(request, booking_reference: str):
    appointment = get_customer_appointment(request.user, booking_reference)
    ctx = _portal_context(appointment)
    ctx['service_ids'] = [line.treatment_id for line in appointment.line_items.all()]
    ctx['staff_id'] = appointment.assigned_staff_id or 'any'
    return render(request, 'accounts/portal/appointment_detail.html', ctx)


@login_required
@require_POST
def appointment_cancel(request, booking_reference: str):
    appointment = get_customer_appointment(request.user, booking_reference)
    try:
        cancel_appointment(appointment)
        messages.success(
            request,
            f'Appointment {appointment.booking_reference} has been cancelled.',
        )
    except PortalError as exc:
        messages.error(request, str(exc))
    return redirect('appointment_list')


@login_required
@require_http_methods(['GET', 'POST'])
@ratelimit(key='user', rate='20/h', method='POST', block=False)
def appointment_reschedule(request, booking_reference: str):
    if getattr(request, 'limited', False) and request.method == 'POST':
        messages.error(request, 'Too many reschedule attempts. Please try again later.')
        return redirect('appointment_detail', booking_reference=booking_reference)

    appointment = get_customer_appointment(request.user, booking_reference)
    ctx = _portal_context(appointment)
    ctx['service_ids'] = [line.treatment_id for line in appointment.line_items.all()]
    ctx['staff_id'] = appointment.assigned_staff_id or 'any'
    ctx['availability_url'] = reverse('bookings:availability')
    ctx['exclude_appointment_id'] = appointment.pk

    if request.method == 'POST':
        date_str = request.POST.get('appointment_date', '').strip()
        time_str = request.POST.get('start_time', '').strip()
        staff_raw = request.POST.get('staff_id', '').strip()

        try:
            new_date = _parse_appointment_date(date_str)
            new_start = _parse_start_time(time_str)
            staff_id = int(staff_raw) if staff_raw and staff_raw.lower() != 'any' else 'any'
            reschedule_appointment(
                appointment,
                new_date=new_date,
                new_start_time=new_start,
                staff_id=staff_id,
            )
            messages.success(request, 'Your appointment has been rescheduled.')
            return redirect('appointment_detail', booking_reference=booking_reference)
        except (ValueError, PortalError) as exc:
            messages.error(request, str(exc))

    return render(request, 'accounts/portal/appointment_reschedule.html', ctx)


@login_required
@require_GET
def appointment_receipt(request, booking_reference: str):
    appointment = get_customer_appointment(request.user, booking_reference)
    ctx = appointment_email_context(appointment)
    ctx['verified_payments'] = appointment.payments.filter(status=PaymentStatus.VERIFIED)
    ctx['print_on_load'] = request.GET.get('print') == '1'
    return render(request, 'accounts/portal/receipt.html', ctx)
