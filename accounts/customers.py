import re
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import CustomerProfile

User = get_user_model()

PHONE_RE = re.compile(r'^\+?[\d\s\-()]{9,20}$')


def normalize_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 9:
        raise ValidationError('Please enter a valid phone number (at least 9 digits).')
    return digits


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]


def build_appointment_notes(
    notes: str = '',
    allergies: str = '',
    first_visit: bool = False,
) -> str:
    sections = []
    if notes.strip():
        sections.append(notes.strip())
    if allergies.strip():
        sections.append('Allergies / preferences:\n' + allergies.strip())
    if first_visit:
        sections.append('First visit: Yes')
    return '\n\n'.join(sections)


def resolve_booking_customer(
    *,
    request_user,
    full_name: str,
    phone: str,
    email: str = '',
) -> User:
    full_name = full_name.strip()
    if not full_name:
        raise ValidationError('Please enter your full name.')
    phone_normalized = normalize_phone(phone)
    email = email.strip().lower()

    if request_user and request_user.is_authenticated:
        user = request_user
        first, last = split_full_name(full_name)
        # Only fill in fields that are not already set — never overwrite existing
        # account data from a booking form, which may contain typos or auto-fill errors.
        fields_to_save = []
        if first and not user.first_name:
            user.first_name = first
            fields_to_save.append('first_name')
        if last and not user.last_name:
            user.last_name = last
            fields_to_save.append('last_name')
        if email and not user.email:
            user.email = email
            fields_to_save.append('email')
        if fields_to_save:
            user.save(update_fields=fields_to_save)
    else:
        # Email is the only reliable identifier for returning guests.
        # Phone numbers can be reassigned by carriers or shared between people,
        # so we never use phone as a deduplication key.
        if email:
            user = User.objects.filter(email__iexact=email).first()
        else:
            user = None

        if user is None:
            # Always create a fresh guest account. Using a UUID suffix prevents
            # two different people with the same phone from sharing one account.
            username = f'guest_{phone_normalized}_{uuid.uuid4().hex[:8]}'
            first, last = split_full_name(full_name)
            user = User.objects.create(
                username=username,
                first_name=first,
                last_name=last,
                email=email,
            )
        else:
            # Returning guest recognised by email — update contact details.
            first, last = split_full_name(full_name)
            user.first_name = first
            user.last_name = last
            user.save(update_fields=['first_name', 'last_name'])

    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    profile.phone = phone_normalized
    profile.full_name = full_name
    profile.save(update_fields=['phone', 'full_name'])

    return user
