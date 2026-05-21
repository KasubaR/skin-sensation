from django.core.exceptions import ValidationError

from bookings.models import Appointment, AppointmentStatus


def user_has_completed_service(user, service) -> bool:
    if not user or not user.is_authenticated or service is None:
        return False
    return Appointment.objects.filter(
        customer=user,
        status=AppointmentStatus.COMPLETED,
        line_items__treatment__service=service,
    ).exists()


def validate_review_eligibility(user, service) -> None:
    if service is None:
        raise ValidationError('Please select a service to review.')
    if not user_has_completed_service(user, service):
        raise ValidationError('You can only review services from completed appointments.')
