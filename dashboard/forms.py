from django import forms
from django.utils.text import slugify

from accounts.models import CustomerNote
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


class AppointmentStatusForm(forms.Form):
  status = forms.ChoiceField(choices=AppointmentStatus.choices)


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


class CustomerNoteForm(forms.ModelForm):
  class Meta:
    model = CustomerNote
    fields = ('body',)
    widgets = {'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add a staff note…'})}


class CustomerSearchForm(forms.Form):
  q = forms.CharField(required=False, max_length=200, label='Search customers')
