from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from accounts.models import CustomerProfile
from bookings.models import Appointment, AppointmentService, AppointmentStatus
from dashboard.activity import get_recent_activity
from payments.models import Payment, PaymentStatus

User = get_user_model()


def _month_start(d: date) -> date:
  return d.replace(day=1)


def _months_back(n: int, from_date: Optional[date] = None) -> list:
  anchor = from_date or timezone.localdate()
  first = _month_start(anchor)
  months = []
  year, month = first.year, first.month
  for _ in range(n):
    months.append(date(year, month, 1))
    month -= 1
    if month < 1:
      month = 12
      year -= 1
  return list(reversed(months))


def get_today_appointments_count() -> int:
  today = timezone.localdate()
  return Appointment.objects.filter(appointment_date=today).exclude(
    status=AppointmentStatus.CANCELLED,
  ).count()


def get_upcoming_appointments_count(days: int = 7) -> int:
  today = timezone.localdate()
  end = today + timedelta(days=days)
  return Appointment.objects.filter(
    appointment_date__gte=today,
    appointment_date__lte=end,
    status__in=(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED),
  ).count()


def get_cancellations_this_month() -> int:
  today = timezone.localdate()
  start = _month_start(today)
  return Appointment.objects.filter(
    status=AppointmentStatus.CANCELLED,
    appointment_date__gte=start,
    appointment_date__lte=today,
  ).count()


def get_pending_payments_count() -> int:
  return Payment.objects.filter(status=PaymentStatus.PENDING).count()


def get_pending_payments_preview(limit: int = 3):
  return Payment.objects.select_related(
    'appointment',
    'appointment__customer',
    'appointment__customer__customer_profile',
  ).filter(status=PaymentStatus.PENDING).order_by('created_at')[:limit]


def get_month_revenue(month: Optional[date] = None) -> Decimal:
  anchor = month or timezone.localdate()
  start = _month_start(anchor)
  _, last_day = monthrange(anchor.year, anchor.month)
  end = anchor.replace(day=last_day)
  total = Payment.objects.filter(
    status=PaymentStatus.VERIFIED,
    verified_at__date__gte=start,
    verified_at__date__lte=end,
  ).aggregate(total=Sum('amount'))['total']
  return total or Decimal('0.00')


def get_new_customers_this_month() -> int:
  today = timezone.localdate()
  start = _month_start(today)
  return CustomerProfile.objects.filter(user__date_joined__date__gte=start).count()


def get_total_customers() -> int:
  return CustomerProfile.objects.count()


def get_today_schedule(limit: int = 5):
  today = timezone.localdate()
  return Appointment.objects.filter(
    appointment_date=today,
  ).exclude(
    status=AppointmentStatus.CANCELLED,
  ).select_related(
    'customer',
    'customer__customer_profile',
    'assigned_staff',
  ).order_by('start_time')[:limit]


def get_top_services(limit: int = 5):
  return (
    AppointmentService.objects.filter(
      appointment__status__in=(
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.COMPLETED,
      ),
    )
    .values('treatment__name')
    .annotate(booking_count=Count('pk'))
    .order_by('-booking_count')[:limit]
  )


def get_overview_context() -> dict:
  cached = cache.get('dashboard:overview')
  if cached is not None:
    return cached
  today = timezone.localdate()
  ctx = {
    'today': today,
    'today_bookings': get_today_appointments_count(),
    'upcoming_bookings': get_upcoming_appointments_count(),
    'cancellations_month': get_cancellations_this_month(),
    'pending_payments_count': get_pending_payments_count(),
    'month_revenue': get_month_revenue(),
    'new_customers_month': get_new_customers_this_month(),
    'total_customers': get_total_customers(),
    'pending_payments_preview': list(get_pending_payments_preview()),
    'today_schedule': list(get_today_schedule()),
    'top_services': list(get_top_services(3)),
    'recent_activity': list(get_recent_activity(10)),
  }
  cache.set('dashboard:overview', ctx, timeout=120)
  return ctx


def get_monthly_revenue_series(months: int = 6) -> dict:
  """Labels and amounts for Chart.js (last N calendar months)."""
  month_starts = _months_back(months)
  labels = []
  amounts = []
  for month_start in month_starts:
    labels.append(month_start.strftime('%b %Y'))
    amounts.append(float(get_month_revenue(month_start)))
  return {'labels': labels, 'amounts': amounts}


def get_appointments_by_status_this_month() -> dict:
  today = timezone.localdate()
  start = _month_start(today)
  qs = (
    Appointment.objects.filter(
      appointment_date__gte=start,
      appointment_date__lte=today,
    )
    .values('status')
    .annotate(count=Count('pk'))
  )
  status_counts = {row['status']: row['count'] for row in qs}
  labels = []
  counts = []
  for value, label in AppointmentStatus.choices:
    labels.append(label)
    counts.append(status_counts.get(value, 0))
  return {'labels': labels, 'counts': counts}


def get_top_treatments_report(limit: int = 5) -> dict:
  rows = list(get_top_services(limit))
  return {
    'labels': [r['treatment__name'] or 'Unknown' for r in rows],
    'counts': [r['booking_count'] for r in rows],
  }


def get_reports_context() -> dict:
  revenue = get_monthly_revenue_series(6)
  status_breakdown = get_appointments_by_status_this_month()
  top_treatments = get_top_treatments_report(5)
  return {
    'chart_revenue_labels': revenue['labels'],
    'chart_revenue_amounts': revenue['amounts'],
    'chart_status_labels': status_breakdown['labels'],
    'chart_status_counts': status_breakdown['counts'],
    'chart_treatment_labels': top_treatments['labels'],
    'chart_treatment_counts': top_treatments['counts'],
    'month_revenue': get_month_revenue(),
    'pending_payments_count': get_pending_payments_count(),
    'today_bookings': get_today_appointments_count(),
  }
