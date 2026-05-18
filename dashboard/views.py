import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.models import CustomerNote, CustomerProfile, Staff
from bookings.models import Appointment, AppointmentStatus
from dashboard.appointment_logic import (
  allowed_next_statuses,
  appointment_list_queryset,
  can_transition,
  filter_appointments,
)
from dashboard.decorators import staff_required
from dashboard.forms import (
  AppointmentFilterForm,
  AppointmentStatusForm,
  CustomerNoteForm,
  CustomerSearchForm,
  ManualPaymentForm,
  PaymentRejectForm,
  ServiceForm,
  TreatmentForm,
)
from notifications.services import notify_appointment_cancelled, notify_appointment_confirmed
from payments.models import Payment, PaymentMethod, PaymentStatus
from payments.services import record_and_verify_payment, reject_payment, verify_payment
from services.models import Service, Treatment


def _staff_choices():
  return [(s.pk, s.display_name) for s in Staff.objects.order_by('display_name')]


def _customer_display(user):
  profile = getattr(user, 'customer_profile', None)
  if profile and profile.full_name:
    return profile.full_name
  return user.get_full_name() or user.email or user.get_username()


def _appointment_queryset():
  return appointment_list_queryset().select_related(
    'customer', 'customer__customer_profile', 'assigned_staff',
  ).prefetch_related('line_items__treatment')


@staff_required
def home(request):
  return redirect('dashboard:appointment_calendar')


@staff_required
@require_GET
def appointment_calendar(request):
  today = timezone.localdate()
  return render(
    request,
    'dashboard/appointments/calendar.html',
    {
      'today': today,
      'filter_form': AppointmentFilterForm(staff_choices=_staff_choices()),
    },
  )


@staff_required
@require_GET
def appointment_calendar_api(request):
  start_raw = request.GET.get('start', '')
  end_raw = request.GET.get('end', '')
  try:
    start_date = datetime.strptime(start_raw[:10], '%Y-%m-%d').date() if start_raw else timezone.localdate()
    end_date = datetime.strptime(end_raw[:10], '%Y-%m-%d').date() if end_raw else start_date + timedelta(days=31)
  except ValueError:
    return JsonResponse({'error': 'Invalid date range.'}, status=400)

  MAX_DAYS = 90
  if (end_date - start_date).days > MAX_DAYS:
    return JsonResponse({'error': 'Date range too large.'}, status=400)

  qs = filter_appointments(_appointment_queryset(), request.GET)
  qs = qs.filter(appointment_date__gte=start_date, appointment_date__lte=end_date)

  events = []
  for appt in qs:
    start_dt = datetime.combine(appt.appointment_date, appt.start_time)
    end_dt = datetime.combine(appt.appointment_date, appt.end_time)
    line_items = list(appt.line_items.all())
    first_service = line_items[0].treatment.name if line_items else ''
    title = f'{_customer_display(appt.customer)}'
    if first_service:
      title = f'{title} — {first_service}'
    events.append({
      'id': appt.booking_reference,
      'title': title,
      'start': start_dt.isoformat(),
      'end': end_dt.isoformat(),
      'status': appt.status,
      'payment_status': appt.payment_status,
      'url': reverse('dashboard:appointment_detail', args=[appt.booking_reference]),
    })
  return JsonResponse(events, safe=False)


@staff_required
@require_GET
def appointment_schedule(request):
  date_raw = request.GET.get('date', '')
  try:
    schedule_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else timezone.localdate()
  except ValueError:
    schedule_date = timezone.localdate()

  appointments = filter_appointments(_appointment_queryset(), request.GET).filter(
    appointment_date=schedule_date,
  ).order_by('start_time')

  return render(
    request,
    'dashboard/appointments/schedule.html',
    {
      'schedule_date': schedule_date,
      'appointments': appointments,
      'filter_form': AppointmentFilterForm(
        staff_choices=_staff_choices(),
        initial=request.GET,
      ),
      'prev_date': schedule_date - timedelta(days=1),
      'next_date': schedule_date + timedelta(days=1),
    },
  )


@staff_required
@require_GET
def appointment_list(request):
  appointments = filter_appointments(_appointment_queryset(), request.GET)
  paginator = Paginator(appointments, 25)
  page = paginator.get_page(request.GET.get('page'))

  return render(
    request,
    'dashboard/appointments/list.html',
    {
      'page_obj': page,
      'filter_form': AppointmentFilterForm(
        staff_choices=_staff_choices(),
        initial=request.GET,
      ),
    },
  )


@staff_required
def appointment_detail(request, booking_reference):
  appointment = get_object_or_404(
    filter_appointments(_appointment_queryset(), {}),
    booking_reference=booking_reference,
  )
  status_form = AppointmentStatusForm(
    initial={'status': appointment.status},
  )
  status_form.fields['status'].choices = [
    (s, label)
    for s, label in AppointmentStatus.choices
    if s == appointment.status or s in allowed_next_statuses(appointment.status)
  ]
  manual_payment_form = ManualPaymentForm(
    initial={'amount': appointment.deposit_amount},
  )
  payments = appointment.payments.select_related('verified_by').order_by('-created_at')

  if request.method == 'POST':
    action = request.POST.get('action', '')
    if action == 'update_status':
      return _handle_status_update(request, appointment)
    if action == 'manual_payment':
      return _handle_manual_payment(request, appointment)

  return render(
    request,
    'dashboard/appointments/detail.html',
    {
      'appointment': appointment,
      'customer_name': _customer_display(appointment.customer),
      'profile': getattr(appointment.customer, 'customer_profile', None),
      'status_form': status_form,
      'manual_payment_form': manual_payment_form,
      'payments': payments,
      'allowed_statuses': allowed_next_statuses(appointment.status),
    },
  )


def _handle_status_update(request, appointment):
  form = AppointmentStatusForm(request.POST)
  if not form.is_valid():
    messages.error(request, 'Invalid status.')
    return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)
  new_status = form.cleaned_data['status']
  if not can_transition(appointment.status, new_status):
    messages.error(request, 'That status change is not allowed.')
    return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)

  old_status = appointment.status
  with transaction.atomic():
    appt = Appointment.objects.select_for_update().get(pk=appointment.pk)
    if not can_transition(appt.status, new_status):
      messages.error(request, 'That status change is no longer allowed.')
      return redirect('dashboard:appointment_detail', booking_reference=appt.booking_reference)
    appt.status = new_status
    appt.save(update_fields=['status'])

  if new_status == AppointmentStatus.CANCELLED and old_status != AppointmentStatus.CANCELLED:
    notify_appointment_cancelled(appt)
  elif new_status == AppointmentStatus.CONFIRMED and old_status != AppointmentStatus.CONFIRMED:
    notify_appointment_confirmed(appt)

  messages.success(request, f'Appointment marked as {appt.get_status_display()}.')
  return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)


def _handle_manual_payment(request, appointment):
  form = ManualPaymentForm(request.POST, request.FILES)
  if not form.is_valid():
    messages.error(request, 'Could not record payment. Check the form and try again.')
    return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)

  try:
    record_and_verify_payment(
      appointment=appointment,
      staff_user=request.user,
      amount=form.cleaned_data['amount'],
      payment_method=form.cleaned_data['payment_method'],
      payment_reference=form.cleaned_data.get('payment_reference', ''),
      proof_of_payment=form.cleaned_data.get('proof_of_payment'),
    )
  except (ValidationError, ValueError) as exc:
    messages.error(request, str(exc))
    return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)

  messages.success(request, 'Payment recorded and verified.')
  return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)


@staff_required
@require_GET
def payment_list(request):
  payments = Payment.objects.select_related(
    'appointment',
    'appointment__customer',
    'appointment__customer__customer_profile',
  ).filter(status=PaymentStatus.PENDING)

  ref = request.GET.get('q', '').strip()
  if ref:
    payments = payments.filter(
      Q(appointment__booking_reference__icontains=ref)
      | Q(payment_reference__icontains=ref),
    )

  method = request.GET.get('payment_method', '').strip()
  if method:
    payments = payments.filter(payment_method=method)

  date_from = request.GET.get('date_from', '').strip()
  try:
    if date_from:
      payments = payments.filter(
        created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date(),
      )
  except ValueError:
    pass

  date_to = request.GET.get('date_to', '').strip()
  try:
    if date_to:
      payments = payments.filter(
        created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date(),
      )
  except ValueError:
    pass

  payments = payments.order_by('created_at')
  paginator = Paginator(payments, 20)
  page = paginator.get_page(request.GET.get('page'))

  return render(
    request,
    'dashboard/payments/list.html',
    {
      'page_obj': page,
      'payment_methods': PaymentMethod.choices,
    },
  )


@staff_required
def payment_detail(request, pk):
  payment = get_object_or_404(
    Payment.objects.select_related(
      'appointment',
      'appointment__customer',
      'appointment__customer__customer_profile',
    ),
    pk=pk,
  )
  reject_form = PaymentRejectForm()

  if request.method == 'POST':
    action = request.POST.get('action', '')
    if action == 'approve':
      try:
        verify_payment(payment, request.user)
        messages.success(request, 'Payment approved.')
      except ValueError as exc:
        messages.error(request, str(exc))
      return redirect('dashboard:payment_detail', pk=pk)

    if action == 'reject':
      reject_form = PaymentRejectForm(request.POST)
      if reject_form.is_valid():
        try:
          reject_payment(
            payment,
            request.user,
            reason=reject_form.cleaned_data.get('rejection_reason', ''),
          )
          messages.success(request, 'Payment rejected.')
        except ValueError as exc:
          messages.error(request, str(exc))
        return redirect('dashboard:payment_detail', pk=pk)
      # invalid form — fall through to re-render with validation errors

  return render(
    request,
    'dashboard/payments/detail.html',
    {
      'payment': payment,
      'appointment': payment.appointment,
      'customer_name': _customer_display(payment.appointment.customer),
      'reject_form': reject_form,
    },
  )


def _treatment_has_future_bookings(treatment):
  return Appointment.objects.filter(
    line_items__treatment=treatment,
    status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
    appointment_date__gte=timezone.localdate(),
  ).exists()


@staff_required
@require_GET
def service_list(request):
  services = Service.objects.annotate(
    treatment_count=Count('treatments'),
  ).order_by('sort_order', 'name')
  return render(request, 'dashboard/services/list.html', {'services': services})


@staff_required
def service_create(request):
  if request.method == 'POST':
    form = ServiceForm(request.POST, request.FILES)
    if form.is_valid():
      form.save()
      messages.success(request, 'Service created.')
      return redirect('dashboard:service_list')
  else:
    form = ServiceForm()
  return render(request, 'dashboard/services/service_form.html', {'form': form, 'is_create': True})


@staff_required
def service_edit(request, pk):
  service = get_object_or_404(Service, pk=pk)
  if request.method == 'POST':
    action = request.POST.get('action', '')
    if action == 'toggle_active':
      if service.is_active and Treatment.objects.filter(
        service=service,
        is_active=True,
      ).exists():
        future = Appointment.objects.filter(
          line_items__treatment__service=service,
          status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
          appointment_date__gte=timezone.localdate(),
        ).exists()
        if future:
          messages.error(request, 'Cannot deactivate: future appointments use this service.')
          return redirect('dashboard:service_edit', pk=pk)
      service.is_active = not service.is_active
      service.save(update_fields=['is_active'])
      messages.success(request, 'Service updated.')
      return redirect('dashboard:service_edit', pk=pk)

    form = ServiceForm(request.POST, request.FILES, instance=service)
    if form.is_valid():
      form.save()
      messages.success(request, 'Service saved.')
      return redirect('dashboard:service_edit', pk=pk)
  else:
    form = ServiceForm(instance=service)

  treatments = service.treatments.order_by('subsection', 'sort_order', 'name')
  return render(
    request,
    'dashboard/services/service_form.html',
    {
      'form': form,
      'service': service,
      'treatments': treatments,
      'is_create': False,
    },
  )


@staff_required
def treatment_create(request):
  service_id = request.GET.get('service')
  initial = {}
  if service_id:
    initial['service'] = service_id
  if request.method == 'POST':
    form = TreatmentForm(request.POST, request.FILES)
    if form.is_valid():
      form.save()
      messages.success(request, 'Treatment created.')
      return redirect('dashboard:service_edit', pk=form.instance.service_id)
  else:
    form = TreatmentForm(initial=initial)
  return render(
    request,
    'dashboard/services/treatment_form.html',
    {'form': form, 'is_create': True},
  )


@staff_required
def treatment_edit(request, pk):
  treatment = get_object_or_404(Treatment, pk=pk)
  if request.method == 'POST':
    action = request.POST.get('action', '')
    if action == 'toggle_active':
      if treatment.is_active and _treatment_has_future_bookings(treatment):
        messages.error(request, 'Cannot deactivate: future appointments include this treatment.')
        return redirect('dashboard:treatment_edit', pk=pk)
      treatment.is_active = not treatment.is_active
      treatment.save(update_fields=['is_active'])
      messages.success(request, 'Treatment updated.')
      return redirect('dashboard:treatment_edit', pk=pk)

    form = TreatmentForm(request.POST, request.FILES, instance=treatment)
    if form.is_valid():
      form.save()
      messages.success(request, 'Treatment saved.')
      return redirect('dashboard:service_edit', pk=treatment.service_id)
  else:
    form = TreatmentForm(instance=treatment)

  return render(
    request,
    'dashboard/services/treatment_form.html',
    {
      'form': form,
      'treatment': treatment,
      'is_create': False,
    },
  )


@staff_required
@require_GET
def customer_list(request):
  form = CustomerSearchForm(request.GET or None)
  profiles = CustomerProfile.objects.select_related('user').annotate(
    visit_count=Count(
      'user__appointments',
      filter=Q(user__appointments__status=AppointmentStatus.COMPLETED),
    ),
  ).order_by('full_name', 'user__email')

  q = ''
  if form.is_valid():
    q = form.cleaned_data.get('q', '').strip()
  if q:
    profiles = profiles.filter(
      Q(full_name__icontains=q)
      | Q(phone__icontains=q)
      | Q(user__email__icontains=q)
      | Q(user__username__icontains=q),
    )

  paginator = Paginator(profiles, 25)
  page = paginator.get_page(request.GET.get('page'))

  return render(
    request,
    'dashboard/customers/list.html',
    {'page_obj': page, 'search_form': form},
  )


@staff_required
def customer_detail(request, user_id):
  from django.contrib.auth import get_user_model

  User = get_user_model()
  customer = get_object_or_404(
    User.objects.select_related('customer_profile'),
    pk=user_id,
  )
  profile = getattr(customer, 'customer_profile', None)
  total_visits = Appointment.objects.filter(
    customer=customer,
    status=AppointmentStatus.COMPLETED,
  ).count()
  appointments = Appointment.objects.filter(customer=customer).select_related(
    'assigned_staff',
  ).prefetch_related('line_items__treatment').order_by('-appointment_date', '-start_time')
  paginator = Paginator(appointments, 15)
  appt_page = paginator.get_page(request.GET.get('page'))

  notes = CustomerNote.objects.filter(customer=customer).select_related('author')

  if request.method == 'POST' and request.POST.get('action') == 'add_note':
    note_form = CustomerNoteForm(request.POST)
    if note_form.is_valid():
      note = note_form.save(commit=False)
      note.customer = customer
      note.author = request.user
      note.save()
      messages.success(request, 'Note added.')
      return redirect('dashboard:customer_detail', user_id=user_id)
  else:
    note_form = CustomerNoteForm()

  return render(
    request,
    'dashboard/customers/detail.html',
    {
      'customer': customer,
      'profile': profile,
      'customer_name': _customer_display(customer),
      'total_visits': total_visits,
      'appt_page': appt_page,
      'notes': notes,
      'note_form': note_form,
    },
  )
