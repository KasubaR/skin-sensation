from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from bookings.models import AppointmentStatus
from bookings.portal import (
    PortalError,
    cancel_appointment,
    get_customer_appointment,
    reschedule_appointment,
)
from notifications.context import appointment_email_context
from payments.models import PaymentStatus
from testimonials.services import get_reviewable_services

from .common import (
    appointments_queryset,
    parse_appointment_date,
    parse_start_time,
    portal_context,
    services_summary,
    split_appointments,
)

FILTER_CHOICES = ('upcoming', 'completed', 'cancelled', 'all')


@login_required
@require_GET
def appointment_list(request):
    active_filter = request.GET.get('filter', 'upcoming')
    if active_filter not in FILTER_CHOICES:
        active_filter = 'upcoming'

    qs = appointments_queryset(request.user)

    if active_filter == 'upcoming':
        upcoming, history = split_appointments(qs)
        upcoming = upcoming.order_by('appointment_date', 'start_time')
        history = history.order_by('-appointment_date', '-start_time')
    elif active_filter == 'completed':
        upcoming = qs.none()
        history = qs.filter(status=AppointmentStatus.COMPLETED).order_by(
            '-appointment_date', '-start_time',
        )
    elif active_filter == 'cancelled':
        upcoming = qs.none()
        history = qs.filter(
            status__in=(AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW),
        ).order_by('-appointment_date', '-start_time')
    else:  # 'all'
        today = timezone.localdate()
        terminal = (
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        )
        upcoming = qs.filter(
            status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
            appointment_date__gte=today,
        ).order_by('appointment_date', 'start_time')
        history = qs.filter(
            Q(appointment_date__lt=today) | Q(status__in=terminal),
        ).order_by('-appointment_date', '-start_time')

    return render(
        request,
        'accounts/portal/appointment_list.html',
        {
            'upcoming': upcoming,
            'history': history,
            'active_filter': active_filter,
            'filter_choices': FILTER_CHOICES,
            'portal_nav': 'appointments',
        },
    )


@login_required
@require_GET
def appointment_detail(request, booking_reference: str):
    appointment = get_customer_appointment(request.user, booking_reference)
    ctx = portal_context(appointment)
    ctx['service_ids'] = [line.treatment_id for line in appointment.line_items.all()]
    ctx['staff_id'] = appointment.assigned_staff_id or 'any'
    ctx['services_summary'] = services_summary(appointment)
    ctx['portal_nav'] = 'appointments'
    if appointment.status == AppointmentStatus.COMPLETED:
        reviewable_ids = set(
            get_reviewable_services(request.user).values_list('pk', flat=True)
        )
        seen = set()
        review_cta_services = []
        for line in appointment.line_items.all():
            service = line.treatment.service
            if service.pk in reviewable_ids and service.pk not in seen:
                seen.add(service.pk)
                review_cta_services.append(service)
        ctx['review_cta_services'] = review_cta_services
    else:
        ctx['review_cta_services'] = []
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
    ctx = portal_context(appointment)
    ctx['service_ids'] = [line.treatment_id for line in appointment.line_items.all()]
    ctx['staff_id'] = appointment.assigned_staff_id or 'any'
    ctx['availability_url'] = reverse('bookings:availability')
    ctx['exclude_appointment_id'] = appointment.pk

    if request.method == 'POST':
        date_str = request.POST.get('appointment_date', '').strip()
        time_str = request.POST.get('start_time', '').strip()
        staff_raw = request.POST.get('staff_id', '').strip()

        try:
            new_date = parse_appointment_date(date_str)
            new_start = parse_start_time(time_str)
            staff_id = int(staff_raw) if staff_raw and staff_raw.lower() != 'any' else None
            reschedule_appointment(
                appointment,
                new_date=new_date,
                new_start_time=new_start,
                staff_id=staff_id,
                user=request.user,
            )
            messages.success(request, 'Your appointment has been rescheduled.')
            return redirect('appointment_detail', booking_reference=booking_reference)
        except (ValueError, PortalError) as exc:
            messages.error(request, str(exc))

    ctx['portal_nav'] = 'appointments'
    return render(request, 'accounts/portal/appointment_reschedule.html', ctx)


@login_required
@require_GET
def appointment_receipt(request, booking_reference: str):
    appointment = get_customer_appointment(request.user, booking_reference)
    ctx = appointment_email_context(appointment)
    payments = appointment.payments.filter(status=PaymentStatus.VERIFIED)
    payment_id = request.GET.get('payment')
    if payment_id:
        try:
            payments = payments.filter(pk=int(payment_id))
        except (TypeError, ValueError):
            pass
    ctx['verified_payments'] = payments
    ctx['print_on_load'] = request.GET.get('print') == '1'
    return render(request, 'accounts/portal/receipt.html', ctx)
