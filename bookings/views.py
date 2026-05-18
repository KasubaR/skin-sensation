import json
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from django_ratelimit.decorators import ratelimit

from accounts.customers import build_appointment_notes, resolve_booking_customer
from accounts.models import Staff
from bookings.models import (
    Appointment,
    AppointmentPaymentStatus,
    AppointmentService,
    AppointmentStatus,
)
from bookings.pricing import calculate_appointment_window
from bookings.scheduling import (
    compute_end_time,
    get_available_slots,
    get_services_by_ids,
    resolve_staff_for_slot,
    slot_is_available,
)
from services.models import Treatment


def _parse_service_ids(request):
    raw = request.GET.get('service_ids', '') or request.POST.get('service_ids', '')
    if not raw and request.content_type == 'application/json':
        try:
            body = json.loads(request.body.decode('utf-8'))
            raw = body.get('service_ids', [])
        except (json.JSONDecodeError, UnicodeDecodeError):
            raw = []
    if isinstance(raw, list):
        return [int(x) for x in raw]
    parts = raw.split(',')
    try:
        return [int(x.strip()) for x in parts if x.strip()]
    except ValueError:
        raise ValueError(f'Invalid service_id in list: {raw!r}')


def _parse_date(value: str):
    return datetime.strptime(value, '%Y-%m-%d').date()


def _parse_time(value: str):
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValidationError('Invalid time format.')


def _staff_image_url(request, staff: Staff):
    if staff.image:
        return request.build_absolute_uri(staff.image.url)
    return None


@require_GET
def staff_list(request):
    try:
        service_ids = _parse_service_ids(request)
    except ValueError:
        return JsonResponse({'error': 'Invalid service_ids.'}, status=400)

    if not service_ids:
        return JsonResponse({'error': 'service_ids is required.'}, status=400)

    from bookings.scheduling import get_eligible_staff

    staff_members = get_eligible_staff(service_ids)
    payload = [
        {
            'id': 'any',
            'display_name': 'Any available',
            'specialization': 'Fastest match',
            'image_url': None,
        },
    ]
    payload.extend(
        {
            'id': staff.pk,
            'display_name': staff.display_name,
            'specialization': staff.specialization,
            'image_url': _staff_image_url(request, staff),
        }
        for staff in staff_members
    )
    return JsonResponse(payload, safe=False)


@require_GET
def calculate_totals(request):
    try:
        service_ids = _parse_service_ids(request)
        services = get_services_by_ids(service_ids)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    window = calculate_appointment_window(services)
    return JsonResponse({
        'total_price': str(window['total_price']),
        'total_duration': window['total_duration'],
        'buffer_minutes': window['buffer_minutes'],
        'appointment_minutes': window['appointment_minutes'],
        'deposit_amount': str(window['deposit_amount']),
    })


def _parse_exclude_appointment_id(request):
    raw = request.GET.get('exclude_appointment_id', '').strip()
    if not raw:
        return None
    try:
        appointment_id = int(raw)
    except ValueError:
        raise ValueError('Invalid exclude_appointment_id.')

    if request.user.is_authenticated:
        owned = Appointment.objects.filter(pk=appointment_id, customer=request.user).exists()
        if not owned:
            raise ValueError('Invalid exclude_appointment_id.')
    else:
        raise ValueError('Authentication required for exclude_appointment_id.')
    return appointment_id


@require_GET
def availability(request):
    date_str = request.GET.get('date', '')
    staff_id = request.GET.get('staff_id', 'any')

    try:
        service_ids = _parse_service_ids(request)
        if not service_ids:
            return JsonResponse({'error': 'service_ids is required.'}, status=400)
        appointment_date = _parse_date(date_str)
        exclude_appointment_id = _parse_exclude_appointment_id(request)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    try:
        result = get_available_slots(
            appointment_date=appointment_date,
            service_ids=service_ids,
            staff_id=staff_id,
            exclude_appointment_id=exclude_appointment_id,
        )
        services = get_services_by_ids(service_ids)
        window = calculate_appointment_window(services)
        result['total_price'] = str(window['total_price'])
        result['deposit_amount'] = str(window['deposit_amount'])
        return JsonResponse(result)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@ratelimit(key='ip', rate='10/h', method='POST', block=False)
@csrf_protect
@require_POST
def create_appointment(request):
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'error': 'Too many booking attempts. Please try again later.'},
            status=429,
        )

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    honeypot = data.get('website', '')
    if honeypot:
        return JsonResponse({'error': 'Invalid submission.'}, status=400)

    try:
        service_ids = [int(x) for x in data.get('service_ids', [])]
        staff_id = data.get('staff_id', 'any')
        appointment_date = _parse_date(data.get('appointment_date', ''))
        start_time = _parse_time(data.get('start_time', ''))
        full_name = (data.get('full_name') or '').strip()
        phone = (data.get('phone') or '').strip()
        email = (data.get('email') or '').strip()
        notes = (data.get('notes') or '').strip()
        allergies = (data.get('allergies') or '').strip()
        first_visit = bool(data.get('first_visit'))
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    if not service_ids:
        return JsonResponse({'error': 'At least one service is required.'}, status=400)

    if appointment_date < timezone.localdate():
        return JsonResponse({'error': 'Appointment date must be today or in the future.'}, status=400)

    try:
        services = get_services_by_ids(service_ids)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    window = calculate_appointment_window(services)
    end_time = compute_end_time(start_time, services)

    try:
        with transaction.atomic():
            # Lock all active appointments for this date so concurrent requests
            # block here and see each other's writes before the availability check.
            Appointment.objects.select_for_update().filter(
                appointment_date=appointment_date,
                status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
            ).values('id')

            staff = resolve_staff_for_slot(
                service_ids=service_ids,
                appointment_date=appointment_date,
                start_time=start_time,
                staff_id=staff_id,
                services=services,
            )
            if not staff:
                return JsonResponse(
                    {'error': 'That time slot is no longer available. Please choose another.'},
                    status=409,
                )

            if not slot_is_available(
                staff=staff,
                appointment_date=appointment_date,
                start_time=start_time,
                services=services,
            ):
                return JsonResponse(
                    {'error': 'That time slot is no longer available. Please choose another.'},
                    status=409,
                )

            customer = resolve_booking_customer(
                request_user=request.user,
                full_name=full_name,
                phone=phone,
                email=email,
            )

            appointment_notes = build_appointment_notes(
                notes=notes,
                allergies=allergies,
                first_visit=first_visit,
            )

            appointment = Appointment.objects.create(
                customer=customer,
                appointment_date=appointment_date,
                start_time=start_time,
                end_time=end_time,
                total_duration=window['total_duration'],
                total_price=window['total_price'],
                deposit_amount=window['deposit_amount'],
                status=AppointmentStatus.PENDING,
                payment_status=AppointmentPaymentStatus.UNPAID,
                assigned_staff=staff,
                notes=appointment_notes,
            )

            for treatment in services:
                AppointmentService.objects.create(
                    appointment=appointment,
                    treatment=treatment,
                    price_snapshot=treatment.price,
                    duration_snapshot=treatment.duration_minutes,
                )

    except ValidationError as exc:
        messages = exc.messages if hasattr(exc, 'messages') else [str(exc)]
        return JsonResponse({'error': messages[0]}, status=400)

    appointment.refresh_from_db()

    from notifications.services import notify_booking_created

    notify_booking_created(appointment)

    return JsonResponse({
        'booking_reference': appointment.booking_reference,
        'total_price': str(appointment.total_price),
        'deposit_amount': str(appointment.deposit_amount),
        'appointment_date': appointment.appointment_date.isoformat(),
        'start_time': appointment.start_time.strftime('%H:%M'),
        'end_time': appointment.end_time.strftime('%H:%M'),
        'staff_name': staff.display_name,
        'staff_id': staff.pk,
        'services': [
            {'name': line.treatment.name, 'price': str(line.price_snapshot)}
            for line in appointment.line_items.select_related('treatment')
        ],
    })
