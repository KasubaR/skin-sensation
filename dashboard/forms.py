from django import forms
from django.utils.text import slugify

from accounts.models import CustomerNote
from communications.models import BusinessInformation, ContactMessage
from bookings.models import AppointmentPaymentStatus, AppointmentStatus
from payments.models import Payment, PaymentMethod
from gallery.models import GalleryImage
from gallery.validators import validate_gallery_image
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
  q = forms.CharField(
    required=False,
    max_length=200,
    label='Search',
    widget=forms.TextInput(
      attrs={
        'class': 'dash-search-input',
        'type': 'search',
        'placeholder': 'Reference, name, email, phone…',
        'aria-label': 'Search appointments',
      },
    ),
  )

  def __init__(self, *args, staff_choices=None, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['payment_status'].choices = [('', 'All payments')] + list(
      AppointmentPaymentStatus.choices,
    )
    self.fields['staff_id'].choices = [('', 'All staff')] + (staff_choices or [])
    for name in ('status', 'payment_status', 'staff_id', 'date_from', 'date_to'):
      self.fields[name].widget.attrs.setdefault('class', 'dash-input')

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
  q = forms.CharField(
    required=False,
    max_length=200,
    label='Search customers',
    widget=forms.TextInput(
      attrs={
        'class': 'dash-search-input',
        'type': 'search',
        'placeholder': 'Name, email, or phone…',
        'aria-label': 'Search customers',
      },
    ),
  )


class ContactMessageStatusForm(forms.ModelForm):
  class Meta:
    model = ContactMessage
    fields = ('status',)


class BusinessSettingsForm(forms.ModelForm):
  hours_monday_friday = forms.CharField(
    label='Monday – Friday',
    max_length=50,
    required=False,
    help_text='e.g. 8:00 am – 6:00 pm',
  )
  hours_saturday = forms.CharField(
    label='Saturday',
    max_length=50,
    required=False,
    help_text='e.g. 9:00 am – 5:00 pm',
  )
  hours_sunday = forms.CharField(
    label='Sunday',
    max_length=50,
    required=False,
    help_text='e.g. 10:00 am – 4:00 pm',
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
      'whatsapp_prefill_message',
      'facebook_url',
      'instagram_url',
      'tiktok_url',
    )
    widgets = {
      'address': forms.Textarea(attrs={'rows': 3}),
      'google_maps_embed_url': forms.Textarea(attrs={'rows': 4}),
      'whatsapp_prefill_message': forms.Textarea(attrs={'rows': 2}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if self.instance and self.instance.pk and self.instance.opening_hours:
      oh = self.instance.opening_hours
      self.fields['hours_monday_friday'].initial = oh.get('monday_friday', '')
      self.fields['hours_saturday'].initial = oh.get('saturday', '')
      self.fields['hours_sunday'].initial = oh.get('sunday', '')
    # Insert opening hours fields between google_maps_embed_url and whatsapp_prefill_message
    field_order = [
      'business_name', 'phone_number', 'whatsapp_number', 'email',
      'address', 'google_maps_embed_url',
      'hours_monday_friday', 'hours_saturday', 'hours_sunday',
      'whatsapp_prefill_message', 'facebook_url', 'instagram_url', 'tiktok_url',
    ]
    self.fields = {k: self.fields[k] for k in field_order}

  def save(self, commit=True):
    instance = super().save(commit=False)
    instance.opening_hours = {
      'monday_friday': self.cleaned_data.get('hours_monday_friday', ''),
      'saturday': self.cleaned_data.get('hours_saturday', ''),
      'sunday': self.cleaned_data.get('hours_sunday', ''),
    }
    if commit:
      instance.save()
    return instance


class GalleryImageForm(forms.ModelForm):
  class Meta:
    model = GalleryImage
    fields = (
      'image',
      'category',
      'caption',
      'alt_text',
      'layout',
      'sort_order',
      'is_active',
    )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    for name in ('image', 'category', 'caption', 'alt_text', 'layout', 'sort_order'):
      if name in self.fields:
        self.fields[name].widget.attrs.setdefault('class', 'dash-input')
    if self.instance and self.instance.pk:
      self.fields['image'].required = False
      self.fields['image'].help_text = 'Leave blank to keep the current image.'

  def clean_image(self):
    image = self.cleaned_data.get('image')
    if image:
      validate_gallery_image(image)
    elif not (self.instance and self.instance.pk and self.instance.image):
      raise forms.ValidationError('An image is required.')
    return image
