from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from bookings.models import Appointment, AppointmentPaymentStatus, AppointmentStatus
from payments.models import Payment, PaymentMethod, PaymentStatus
from payments.services import _verified_total

User = get_user_model()

MAX_PROOF_BYTES = 5 * 1024 * 1024
ALLOWED_PROOF_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


class CustomerPaymentError(Exception):
    """Customer payment action could not be completed."""


def get_customer_payments(user: User):
    return (
        Payment.objects.filter(appointment__customer=user)
        .select_related('appointment', 'appointment__assigned_staff')
        .order_by('-created_at')
    )


def get_customer_payment(user: User, payment_id: int) -> Payment:
    return get_object_or_404(
        get_customer_payments(user),
        pk=payment_id,
    )


def remaining_balance(appointment: Appointment) -> Decimal:
    verified = _verified_total(appointment)
    return max(appointment.total_price - verified, Decimal('0'))


def deposit_outstanding(appointment: Appointment) -> Decimal:
    verified = _verified_total(appointment)
    if appointment.deposit_amount <= 0:
        return Decimal('0')
    return max(appointment.deposit_amount - verified, Decimal('0'))


def can_upload_proof(appointment: Appointment) -> bool:
    if appointment.status in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.COMPLETED,
    ):
        return False
    if appointment.payment_status == AppointmentPaymentStatus.PAID:
        return False
    if appointment.payments.filter(status=PaymentStatus.PENDING).exists():
        return False
    return deposit_outstanding(appointment) > 0 or remaining_balance(appointment) > 0


def _validate_proof_file(proof_file) -> None:
    if not proof_file:
        raise ValidationError('Payment proof image is required.')
    if proof_file.size > MAX_PROOF_BYTES:
        raise ValidationError('Image must be 5 MB or smaller.')
    content_type = getattr(proof_file, 'content_type', '') or ''
    if content_type and content_type not in ALLOWED_PROOF_TYPES:
        raise ValidationError('Upload a JPEG, PNG, or WebP image.')


@transaction.atomic
def create_customer_payment(
    *,
    appointment: Appointment,
    user: User,
    amount: Decimal,
    payment_method: str,
    payment_reference: str = '',
    proof_file=None,
) -> Payment:
    if appointment.customer_id != user.id:
        raise CustomerPaymentError('You do not have access to this appointment.')

    if not can_upload_proof(appointment):
        raise CustomerPaymentError(
            'A payment is already pending review or this appointment does not accept new payments.'
        )

    try:
        _validate_proof_file(proof_file)
    except ValidationError as exc:
        raise CustomerPaymentError(exc.messages[0] if exc.messages else str(exc)) from exc

    outstanding = remaining_balance(appointment)
    if amount <= 0:
        raise CustomerPaymentError('Amount must be greater than zero.')
    if amount > outstanding:
        raise CustomerPaymentError(
            f'Amount cannot exceed the remaining balance of K{outstanding}.'
        )

    if payment_method not in PaymentMethod.values:
        raise CustomerPaymentError('Invalid payment method.')

    payment = Payment.objects.create(
        appointment=appointment,
        amount=amount,
        payment_method=payment_method,
        payment_reference=payment_reference or appointment.booking_reference,
        proof_of_payment=proof_file,
        status=PaymentStatus.PENDING,
    )

    from notifications.services import notify_payment_received

    notify_payment_received(payment)
    return payment
