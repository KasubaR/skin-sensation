import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
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
from bookings.portal import PortalError, reschedule_appointment
from dashboard.activity import log_staff_activity
from dashboard.appointment_logic import (
  allowed_next_statuses,
  appointment_list_queryset,
  can_transition,
  filter_appointments,
)
from dashboard.decorators import staff_required
from dashboard.forms import (
  AppointmentFilterForm,
  AppointmentRescheduleForm,
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
from dashboard.models import StaffActivityLog
from dashboard.stats import get_overview_context, get_reports_context
from payments.services import record_and_verify_payment, reject_payment, verify_payment
from services.models import Service, Treatment

User = get_user_model()
logger = logging.getLogger(__name__)


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
@require_GET
def home(request):
  context = get_overview_context()
  return render(request, 'dashboard/overview.html', context)


@staff_required
@require_GET
def reports(request):
  context = get_reports_context()
  context['chart_revenue_labels'] = json.dumps(context['chart_revenue_labels'])
  context['chart_revenue_amounts'] = json.dumps(context['chart_revenue_amounts'])
  context['chart_status_labels'] = json.dumps(context['chart_status_labels'])
  context['chart_status_counts'] = json.dumps(context['chart_status_counts'])
  context['chart_treatment_labels'] = json.dumps(context['chart_treatment_labels'])
  context['chart_treatment_counts'] = json.dumps(context['chart_treatment_counts'])
  return render(request, 'dashboard/reports.html', context)


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
  can_reschedule = appointment.status in (
    AppointmentStatus.PENDING,
    AppointmentStatus.CONFIRMED,
  )
  staff_choices = _staff_choices()
  reschedule_form = AppointmentRescheduleForm(
    staff_choices=staff_choices,
    initial={
      'appointment_date': appointment.appointment_date,
      'start_time': appointment.start_time,
      'staff_id': str(appointment.assigned_staff_id) if appointment.assigned_staff_id else '',
    },
  )

  if request.method == 'POST':
    action = request.POST.get('action', '')
    if action == 'update_status':
      return _handle_status_update(request, appointment)
    if action == 'manual_payment':
      return _handle_manual_payment(request, appointment)
    if action == 'reschedule':
      return _handle_reschedule(request, appointment, staff_choices)

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
      'can_reschedule': can_reschedule,
      'reschedule_form': reschedule_form,
    },
  )


def _send_status_notifications(new_status, old_status, appt):
    try:
        if new_status == AppointmentStatus.CANCELLED and old_status != AppointmentStatus.CANCELLED:
            notify_appointment_cancelled(appt)
        elif new_status == AppointmentStatus.CONFIRMED and old_status != AppointmentStatus.CONFIRMED:
            notify_appointment_confirmed(appt)
    except Exception:
        logger.exception('Failed to send status notification for appointment %s', appt.booking_reference)


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
    transaction.on_commit(lambda: _send_status_notifications(new_status, old_status, appt))

  log_staff_activity(
    user=request.user,
    action=StaffActivityLog.Action.APPOINTMENT_STATUS,
    target_type='appointment',
    target_id=appt.booking_reference,
    message=f'Changed {appt.booking_reference} from {old_status} to {new_status}',
  )
  messages.success(request, f'Appointment marked as {appt.get_status_display()}.')
  return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)


def _handle_reschedule(request, appointment, staff_choices):
  form = AppointmentRescheduleForm(request.POST, staff_choices=staff_choices)
  if not form.is_valid():
    messages.error(request, 'Could not reschedule. Check the form and try again.')
    return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)

  staff_raw = form.cleaned_data.get('staff_id') or ''
  staff_id = int(staff_raw) if staff_raw else None

  try:
    reschedule_appointment(
      appointment,
      new_date=form.cleaned_data['appointment_date'],
      new_start_time=form.cleaned_data['start_time'],
      staff_id=staff_id,
      staff_override=True,
    )
  except PortalError as exc:
    messages.error(request, str(exc))
    return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)

  log_staff_activity(
    user=request.user,
    action=StaffActivityLog.Action.APPOINTMENT_RESCHEDULED,
    target_type='appointment',
    target_id=appointment.booking_reference,
    message=f'Rescheduled {appointment.booking_reference} to {form.cleaned_data["appointment_date"]}',
  )
  messages.success(request, 'Appointment rescheduled.')
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

  log_staff_activity(
    user=request.user,
    action=StaffActivityLog.Action.PAYMENT_RECORDED,
    target_type='appointment',
    target_id=appointment.booking_reference,
    message=f'Recorded manual payment for {appointment.booking_reference}',
  )
  messages.success(request, 'Payment recorded and verified.')
  return redirect('dashboard:appointment_detail', booking_reference=appointment.booking_reference)


_PAYMENT_STATUS_TABS = [
  (PaymentStatus.PENDING, 'Pending'),
  (PaymentStatus.VERIFIED, 'Verified'),
  (PaymentStatus.FAILED, 'Failed'),
  (PaymentStatus.REFUNDED, 'Refunded'),
]


@staff_required
@require_GET
def payment_list(request):
  status_filter = request.GET.get('status', PaymentStatus.PENDING).strip()
  valid_statuses = {s for s, _ in PaymentStatus.choices}
  if status_filter not in valid_statuses:
    status_filter = PaymentStatus.PENDING

  payments = Payment.objects.select_related(
    'appointment',
    'appointment__customer',
    'appointment__customer__customer_profile',
  ).filter(status=status_filter)

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

  status_label = dict(PaymentStatus.choices).get(status_filter, status_filter)

  return render(
    request,
    'dashboard/payments/list.html',
    {
      'page_obj': page,
      'payment_methods': PaymentMethod.choices,
      'status_filter': status_filter,
      'status_label': status_label,
      'status_tabs': _PAYMENT_STATUS_TABS,
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
        log_staff_activity(
          user=request.user,
          action=StaffActivityLog.Action.PAYMENT_VERIFIED,
          target_type='payment',
          target_id=str(payment.pk),
          message=f'Verified payment #{payment.pk} for {payment.appointment.booking_reference}',
        )
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
          log_staff_activity(
            user=request.user,
            action=StaffActivityLog.Action.PAYMENT_REJECTED,
            target_type='payment',
            target_id=str(payment.pk),
            message=f'Rejected payment #{payment.pk} for {payment.appointment.booking_reference}',
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
      with transaction.atomic():
        service = Service.objects.select_for_update().get(pk=pk)
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
      log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.SERVICE_TOGGLED,
        target_type='service',
        target_id=str(service.pk),
        message=f'Service "{service.name}" set to {"active" if service.is_active else "inactive"}',
      )
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
      with transaction.atomic():
        treatment = Treatment.objects.select_for_update().get(pk=pk)
        if treatment.is_active and _treatment_has_future_bookings(treatment):
          messages.error(request, 'Cannot deactivate: future appointments include this treatment.')
          return redirect('dashboard:treatment_edit', pk=pk)
        treatment.is_active = not treatment.is_active
        treatment.save(update_fields=['is_active'])
      log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.TREATMENT_TOGGLED,
        target_type='treatment',
        target_id=str(treatment.pk),
        message=f'Treatment "{treatment.name}" set to {"active" if treatment.is_active else "inactive"}',
      )
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
  customer = get_object_or_404(
    User.objects.select_related('customer_profile').filter(is_staff=False),
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
      log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.CUSTOMER_NOTE_ADDED,
        target_type='customer',
        target_id=str(user_id),
        message=f'Added note to customer #{user_id}',
      )
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
