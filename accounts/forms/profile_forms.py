from django import forms
from django.contrib.auth import get_user_model

from accounts.models import CustomerProfile

User = get_user_model()

MAX_AVATAR_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def _validate_image(image_field):
    if not image_field:
        return
    if image_field.size > MAX_AVATAR_BYTES:
        raise forms.ValidationError('Image must be 2 MB or smaller.')
    content_type = getattr(image_field, 'content_type', '') or ''
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise forms.ValidationError('Upload a JPEG, PNG, or WebP image.')


class ProfileEditForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'portal-input'}),
    )

    class Meta:
        model = CustomerProfile
        fields = ('full_name', 'phone', 'avatar')
        widgets = {
            'full_name': forms.TextInput(attrs={
                'autocomplete': 'name',
                'class': 'portal-input',
            }),
            'phone': forms.TextInput(attrs={
                'autocomplete': 'tel',
                'class': 'portal-input',
            }),
            'avatar': forms.FileInput(attrs={'class': 'portal-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user:
            self.fields['email'].initial = user.email

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        _validate_image(avatar)
        return avatar

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.user.pk)
            .exists()
        ):
            raise forms.ValidationError('This email is already in use.')
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        new_email = self.cleaned_data['email']
        if new_email != (self.user.email or '').lower():
            self.user.email = new_email
            if commit:
                self.user.save(update_fields=['email'])
        if commit:
            profile.save()
        return profile


class NotificationPreferencesForm(forms.Form):
    email_payments = forms.BooleanField(required=False, label='Payment updates')
    email_bookings = forms.BooleanField(required=False, label='Booking updates')
    email_reminders = forms.BooleanField(required=False, label='Appointment reminders')

    def __init__(self, *args, profile: CustomerProfile = None, **kwargs):
        super().__init__(*args, **kwargs)
        prefs = (profile.notification_preferences or {}) if profile else {}
        email_prefs = prefs.get('email', {})
        self.fields['email_payments'].initial = email_prefs.get('payments', True)
        self.fields['email_bookings'].initial = email_prefs.get('bookings', True)
        self.fields['email_reminders'].initial = email_prefs.get('reminders', True)

    def to_preferences(self) -> dict:
        return {
            'email': {
                'payments': self.cleaned_data.get('email_payments', True),
                'bookings': self.cleaned_data.get('email_bookings', True),
                'reminders': self.cleaned_data.get('email_reminders', True),
            },
        }
