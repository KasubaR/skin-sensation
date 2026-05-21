from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from bookings.portal import get_customer_appointment
from payments.customer import (
    CustomerPaymentError,
    can_upload_proof,
    create_customer_payment,
    deposit_outstanding,
    get_customer_payment,
    get_customer_payments,
    remaining_balance,
)
from payments.models import PaymentMethod, PaymentStatus
from payments.receipts import generate_payment_receipt_pdf

from .common import portal_context


@login_required
@require_GET
def payment_list(request):
    payments = get_customer_payments(request.user)
    status_filter = request.GET.get('status', '').strip().upper()
    if status_filter in PaymentStatus.values:
        payments = payments.filter(status=status_filter)
    return render(
        request,
        'accounts/portal/payments/list.html',
        {
            'payments': payments,
            'active_status': status_filter,
            'status_choices': PaymentStatus.choices,
            'portal_nav': 'payments',
        },
    )


@login_required
@require_GET
def payment_detail(request, payment_id: int):
    payment = get_customer_payment(request.user, payment_id)
    appointment = payment.appointment
    return render(
        request,
        'accounts/portal/payments/detail.html',
        {
            'payment': payment,
            'appointment': appointment,
            'remaining_balance': remaining_balance(appointment),
            'portal_nav': 'payments',
        },
    )


@login_required
@require_GET
def payment_receipt_pdf(request, payment_id: int):
    payment = get_customer_payment(request.user, payment_id)
    if payment.status != PaymentStatus.VERIFIED:
        messages.error(request, 'Receipts are available only for verified payments.')
        return redirect('payment_detail', payment_id=payment.pk)

    pdf_bytes = generate_payment_receipt_pdf(payment)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f'receipt-{payment.appointment.booking_reference}-{payment.pk}.pdf'
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET', 'POST'])
@ratelimit(key='user', rate='10/h', method='POST', block=False)
def payment_upload(request, booking_reference: str):
    if getattr(request, 'limited', False) and request.method == 'POST':
        messages.error(request, 'Too many upload attempts. Please try again later.')
        return redirect('appointment_detail', booking_reference=booking_reference)

    appointment = get_customer_appointment(request.user, booking_reference)
    ctx = portal_context(appointment)
    ctx['portal_nav'] = 'payments'
    ctx['payment_methods'] = PaymentMethod.choices
    ctx['suggested_amount'] = deposit_outstanding(appointment) or remaining_balance(appointment)

    if not can_upload_proof(appointment):
        messages.info(request, 'This appointment does not require a new payment upload.')
        return redirect('appointment_detail', booking_reference=booking_reference)

    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '').strip()
        method = request.POST.get('payment_method', '').strip()
        reference = request.POST.get('payment_reference', '').strip()
        proof = request.FILES.get('proof_of_payment')

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, 'Enter a valid amount.')
            return render(request, 'accounts/portal/payments/upload.html', ctx)

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return render(request, 'accounts/portal/payments/upload.html', ctx)

        try:
            create_customer_payment(
                appointment=appointment,
                user=request.user,
                amount=amount,
                payment_method=method,
                payment_reference=reference,
                proof_file=proof,
            )
            messages.success(
                request,
                'Payment proof submitted. We will review it and confirm shortly.',
            )
            return redirect('payment_list')
        except CustomerPaymentError as exc:
            messages.error(request, str(exc))

    return render(request, 'accounts/portal/payments/upload.html', ctx)
