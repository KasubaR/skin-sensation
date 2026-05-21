import threading

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

from communications.forms import ContactForm
from notifications.services import send_contact_notification


def _notify_contact(pk):
    from communications.models import ContactMessage
    try:
        msg = ContactMessage.objects.get(pk=pk)
    except ContactMessage.DoesNotExist:
        return
    send_contact_notification(msg)


@method_decorator(
    ratelimit(key='ip', rate='5/h', method='POST', block=True),
    name='post',
)
class ContactView(FormView):
    template_name = 'contact.html'
    form_class = ContactForm
    success_url = reverse_lazy('contact_success')

    def form_valid(self, form):
        contact_message = form.save()
        pk = contact_message.pk
        transaction.on_commit(
            lambda: threading.Thread(target=_notify_contact, args=(pk,), daemon=True).start()
        )
        self.request.session['contact_submitted'] = True
        messages.success(self.request, 'Message sent successfully.')
        return super().form_valid(form)


class ContactSuccessView(TemplateView):
    template_name = 'contact_success.html'

    def get(self, request, *args, **kwargs):
        if not request.session.pop('contact_submitted', False):
            return redirect('contact')
        return super().get(request, *args, **kwargs)
