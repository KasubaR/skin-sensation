from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from bookings.models import AppointmentPaymentStatus
from payments.models import Payment, PaymentStatus


def _verified_total(appointment):
  return sum(
    p.amount
    for p in appointment.payments.filter(status=PaymentStatus.VERIFIED)
  )


def sync_appointment_payment_status(appointment):
  verified = _verified_total(appointment)
  if verified >= appointment.total_price:
    new_status = AppointmentPaymentStatus.PAID
  elif verified >= appointment.deposit_amount and appointment.deposit_amount > 0:
    new_status = AppointmentPaymentStatus.DEPOSIT_PAID
  else:
    new_status = AppointmentPaymentStatus.UNPAID

  if appointment.payment_status != new_status:
    appointment.payment_status = new_status
    appointment.save(update_fields=['payment_status'])


@transaction.atomic
def verify_payment(payment: Payment, staff_user) -> Payment:
  payment = Payment.objects.select_for_update().select_related('appointment').get(pk=payment.pk)
  if payment.status != PaymentStatus.PENDING:
    raise ValueError('Only pending payments can be verified.')

  payment.status = PaymentStatus.VERIFIED
  payment.verified_by = staff_user
  payment.verified_at = timezone.now()
  payment.save(update_fields=['status', 'verified_by', 'verified_at'])

  sync_appointment_payment_status(payment.appointment)

  from notifications.services import notify_payment_verified

  notify_payment_verified(payment)
  return payment


@transaction.atomic
def reject_payment(payment: Payment, staff_user, reason: str = '') -> Payment:
  payment = Payment.objects.select_for_update().select_related('appointment').get(pk=payment.pk)
  if payment.status != PaymentStatus.PENDING:
    raise ValueError('Only pending payments can be rejected.')

  payment.status = PaymentStatus.FAILED
  # Payment model has no separate rejected_by/rejected_at fields;
  # verified_by/verified_at serve as the actor/timestamp for both outcomes.
  payment.verified_by = staff_user
  payment.verified_at = timezone.now()
  if reason:
    payment.rejection_reason = reason[:2000]
  payment.save(
    update_fields=['status', 'verified_by', 'verified_at', 'rejection_reason'],
  )
  sync_appointment_payment_status(payment.appointment)

  from notifications.services import notify_payment_rejected

  notify_payment_rejected(payment)
  return payment


@transaction.atomic
def record_and_verify_payment(
  *,
  appointment,
  staff_user,
  amount: Decimal,
  payment_method: str,
  payment_reference: str = '',
  proof_of_payment=None,
) -> Payment:
  # Create and immediately verify in one transaction without re-fetching via
  # select_for_update (the row is brand-new; no concurrent access is possible).
  payment = Payment.objects.create(
    appointment=appointment,
    amount=amount,
    payment_method=payment_method,
    payment_reference=payment_reference,
    proof_of_payment=proof_of_payment or '',
    status=PaymentStatus.VERIFIED,
  )
  payment.verified_by = staff_user
  payment.verified_at = timezone.now()
  payment.save(update_fields=['verified_by', 'verified_at'])
  sync_appointment_payment_status(appointment)

  from notifications.services import notify_payment_verified

  notify_payment_verified(payment)
  return payment
