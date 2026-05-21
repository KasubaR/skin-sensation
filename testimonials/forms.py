from django import forms
from django.core.exceptions import ValidationError

from services.models import Service
from testimonials.models import Testimonial
from testimonials.services import get_reviewable_services, submit_review


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ('service', 'rating', 'title', 'review')
        widgets = {
            'service': forms.Select(attrs={'class': 'testimonials-select'}),
            'rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'review': forms.Textarea(attrs={'rows': 5, 'class': 'testimonials-textarea'}),
            'title': forms.TextInput(
                attrs={'placeholder': 'Optional headline', 'class': 'testimonials-input'},
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = (
            get_reviewable_services(user) if user else Service.objects.none()
        )
        self.fields['service'].empty_label = 'Select a service'
        self.fields['rating'].required = True
        self.fields['review'].required = True
        self.fields['title'].required = False

    def save(self, commit=True):
        if not self.user:
            raise ValidationError('You must be logged in to submit a review.')
        return submit_review(
            self.user,
            service=self.cleaned_data['service'],
            rating=self.cleaned_data['rating'],
            title=self.cleaned_data.get('title', ''),
            review=self.cleaned_data['review'],
        )
