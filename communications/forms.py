from django import forms
from django.core.validators import MaxLengthValidator, MinLengthValidator

from communications.models import ContactMessage, SUBJECT_CHOICES

_SUBJECT_WIDGET_CHOICES = [('', 'Select a topic…')] + SUBJECT_CHOICES


class ContactForm(forms.ModelForm):
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
    )

    class Meta:
        model = ContactMessage
        fields = ('full_name', 'email', 'phone_number', 'subject', 'message')
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Your name',
                'autocomplete': 'name',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'you@example.com',
                'autocomplete': 'email',
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+260 9XX XXX XXX',
                'autocomplete': 'tel',
            }),
            'subject': forms.Select(choices=_SUBJECT_WIDGET_CHOICES),
            'message': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'How can we help?',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].label = 'Full name'
        self.fields['email'].label = 'Email address'
        self.fields['phone_number'].label = 'Phone number'
        self.fields['phone_number'].validators.append(MinLengthValidator(8))
        self.fields['message'].validators.append(MaxLengthValidator(5000))
        self.fields['subject'].required = True

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Invalid submission.')
        return ''

