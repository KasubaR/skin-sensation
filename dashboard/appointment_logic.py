from django.db.models import Q

from bookings.models import Appointment, AppointmentStatus


ALLOWED_STATUS_TRANSITIONS = {
  AppointmentStatus.PENDING: {
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.CANCELLED,
  },
  AppointmentStatus.CONFIRMED: {
    AppointmentStatus.COMPLETED,
    AppointmentStatus.CANCELLED,
    AppointmentStatus.NO_SHOW,
  },
}


def allowed_next_statuses(current_status):
  return ALLOWED_STATUS_TRANSITIONS.get(current_status, set())


def can_transition(current_status, new_status):
  return new_status in allowed_next_statuses(current_status)


def filter_appointments(queryset, params):
  status = params.get('status', '').strip()
  if status:
    queryset = queryset.filter(status=status)

  payment_status = params.get('payment_status', '').strip()
  if payment_status:
    queryset = queryset.filter(payment_status=payment_status)

  staff_id = params.get('staff_id', '').strip()
  if staff_id:
    queryset = queryset.filter(assigned_staff_id=staff_id)

  date_from = params.get('date_from', '').strip()
  if date_from:
    queryset = queryset.filter(appointment_date__gte=date_from)

  date_to = params.get('date_to', '').strip()
  if date_to:
    queryset = queryset.filter(appointment_date__lte=date_to)

  q = params.get('q', '').strip()
  if q:
    queryset = queryset.filter(
      Q(booking_reference__icontains=q)
      | Q(customer__email__icontains=q)
      | Q(customer__username__icontains=q)
      | Q(customer__customer_profile__full_name__icontains=q)
      | Q(customer__customer_profile__phone__icontains=q)
      | Q(notes__icontains=q)
    )

  return queryset


def appointment_list_queryset():
  return Appointment.objects.all().order_by('-appointment_date', '-start_time')
