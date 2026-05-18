from decimal import Decimal

from services.models import Treatment

BUFFER_MINUTES = 15
SLOT_INTERVAL_MINUTES = 60
DEPOSIT_MIN = Decimal('50.00')
DEPOSIT_RATE = Decimal('0.20')


def calculate_total_price(treatments: list[Treatment]) -> Decimal:
    return sum((t.price for t in treatments), Decimal('0.00'))


def calculate_total_duration(treatments: list[Treatment]) -> int:
    return sum(t.duration_minutes for t in treatments)


def calculate_buffer_minutes(treatments: list[Treatment]) -> int:
    return BUFFER_MINUTES if treatments else 0


def calculate_appointment_minutes(treatments: list[Treatment]) -> int:
    return calculate_total_duration(treatments) + calculate_buffer_minutes(treatments)


def calculate_deposit(total_price: Decimal) -> Decimal:
    return max(DEPOSIT_MIN, (total_price * DEPOSIT_RATE).quantize(Decimal('0.01')))


def calculate_appointment_window(treatments: list[Treatment]) -> dict:
    total_price = calculate_total_price(treatments)
    total_duration = calculate_total_duration(treatments)
    buffer_minutes = calculate_buffer_minutes(treatments)
    appointment_minutes = total_duration + buffer_minutes
    return {
        'total_price': total_price,
        'total_duration': total_duration,
        'buffer_minutes': buffer_minutes,
        'appointment_minutes': appointment_minutes,
        'deposit_amount': calculate_deposit(total_price),
    }
