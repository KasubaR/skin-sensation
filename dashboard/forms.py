import json

from django import forms
from django.utils.text import slugify

from accounts.models import CustomerNote
from communications.models import BusinessInformation, ContactMessage
from bookings.models import AppointmentPaymentStatus, AppointmentStatus
from payments.models import Payment, PaymentMethod
from services.models import Service, Treatment


class AppointmentFilterForm(forms.Form):
  status = forms.ChoiceField(
    required=False,
    choices=[('', 'All statuses')] + list(AppointmentStatus.choices),
  )
  payment_status = forms.ChoiceField(required=False)
  staff_id = forms.ChoiceField(required=False, choices=[])
  date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
  date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
  q = forms.CharField(required=False, max_length=200, label='Search')

  def __init__(self, *args, staff_choices=None, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['payment_status'].choices = [('', 'All payments')] + list(
      AppointmentPaymentStatus.choices,
    )
    self.fields['staff_id'].choices = [('', 'All staff')] + (staff_choices or [])

  def clean(self):
    cleaned = super().clean()
    date_from = cleaned.get('date_from')
    date_to = cleaned.get('date_to')
    if date_from and date_to and date_from > date_to:
      raise forms.ValidationError('"From" date must be before "To" date.')
    return cleaned


class AppointmentStatusForm(forms.Form):
  status = forms.ChoiceField(choices=AppointmentStatus.choices)


class AppointmentRescheduleForm(forms.Form):
  appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
  start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
  staff_id = forms.ChoiceField(required=False, label='Therapist')

  def __init__(self, *args, staff_choices=None, **kwargs):
    super().__init__(*args, **kwargs)
    choices = [('', 'Any available')] + (staff_choices or [])
    self.fields['staff_id'].choices = choices


class ServiceForm(forms.ModelForm):
  class Meta:
    model = Service
    fields = (
      'name',
      'slug',
      'description',
      'tagline',
      'image',
      'sort_order',
      'is_active',
    )
    widgets = {
      'description': forms.Textarea(attrs={'rows': 4}),
    }

  def clean_slug(self):
    slug = self.cleaned_data.get('slug') or ''
    if not slug and self.cleaned_data.get('name'):
      slug = slugify(self.cleaned_data['name'])
    if slug:
      qs = Service.objects.filter(slug=slug)
      if self.instance and self.instance.pk:
        qs = qs.exclude(pk=self.instance.pk)
      if qs.exists():
        raise forms.ValidationError(
          f'The slug "{slug}" is already in use. Please choose a different one.'
        )
    return slug


class TreatmentForm(forms.ModelForm):
  class Meta:
    model = Treatment
    fields = (
      'service',
      'name',
      'slug',
      'description',
      'benefits',
      'duration_minutes',
      'price',
      'price_from',
      'price_label',
      'image',
      'subsection',
      'is_featured',
      'is_active',
      'sort_order',
    )
    widgets = {
      'description': forms.Textarea(attrs={'rows': 3}),
      'benefits': forms.Textarea(attrs={'rows': 3}),
    }

  def clean_slug(self):
    slug = self.cleaned_data.get('slug') or ''
    if not slug and self.cleaned_data.get('name'):
      slug = slugify(self.cleaned_data['name'])
    if slug:
      qs = Treatment.objects.filter(slug=slug)
      if self.instance and self.instance.pk:
        qs = qs.exclude(pk=self.instance.pk)
      if qs.exists():
        raise forms.ValidationError(
          f'The slug "{slug}" is already in use. Please choose a different one.'
        )
    return slug


class PaymentRejectForm(forms.Form):
  rejection_reason = forms.CharField(
    required=False,
    widget=forms.Textarea(attrs={'rows': 3}),
    label='Reason (optional)',
  )


class ManualPaymentForm(forms.Form):
  amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=10)
  payment_method = forms.ChoiceField(choices=PaymentMethod.choices)
  payment_reference = forms.CharField(required=False, max_length=255)
  proof_of_payment = forms.ImageField(required=False)

  _ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

  def clean_proof_of_payment(self):
    image = self.cleaned_data.get('proof_of_payment')
    if image:
      if image.size > 5 * 1024 * 1024:
        raise forms.ValidationError('Image must be under 5 MB.')
      if getattr(image, 'content_type', None) not in self._ALLOWED_IMAGE_TYPES:
        raise forms.ValidationError('Only JPEG, PNG, or WebP images are allowed.')
    return image


class CustomerNoteForm(forms.ModelForm):
  class Meta:
    model = CustomerNote
    fields = ('body',)
    widgets = {'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add a staff note…'})}


class CustomerSearchForm(forms.Form):
  q = forms.CharField(required=False, max_length=200, label='Search customers')


class ContactMessageStatusForm(forms.ModelForm):
  class Meta:
    model = ContactMessage
    fields = ('status',)


class BusinessSettingsForm(forms.ModelForm):
  opening_hours = forms.CharField(
    widget=forms.Textarea(attrs={'rows': 5}),
    help_text='JSON object, e.g. {"monday_friday": "8:00 am – 6:00 pm", ...}',
  )

  class Meta:
    model = BusinessInformation
    fields = (
      'business_name',
      'phone_number',
      'whatsapp_number',
      'email',
      'address',
      'google_maps_embed_url',
      'opening_hours',
      'whatsapp_prefill_message',
      'facebook_url',
      'instagram_url',
      'tiktok_url',
    )
    widgets = {
      'address': forms.Textarea(attrs={'rows': 3}),
      'google_maps_embed_url': forms.Textarea(attrs={'rows': 2}),
      'whatsapp_prefill_message': forms.Textarea(attrs={'rows': 2}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if self.instance and self.instance.pk and self.instance.opening_hours:
      self.fields['opening_hours'].initial = json.dumps(
        self.instance.opening_hours,
        indent=2,
      )

  def clean_opening_hours(self):
    value = self.cleaned_data.get('opening_hours', '')
    if isinstance(value, dict):
      data = value
    else:
      try:
        data = json.loads(value)
      except json.JSONDecodeError as exc:
        raise forms.ValidationError('Enter valid JSON for opening hours.') from exc
    if not isinstance(data, dict) or not all(
      isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
      raise forms.ValidationError(
        'Opening hours must be a JSON object with string keys and values.'
      )
    return data
