from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation


@require_POST
@login_required
@ratelimit(key='user', rate='3/h', method='POST', block=False)
def resend_confirmation_email(request):
    if getattr(request, 'limited', False):
        messages.error(
            request,
            'Too many requests. Please wait before requesting another confirmation email.',
        )
        return redirect('account_email_verification_sent')

    try:
        EmailAddress.objects.get(user=request.user, verified=False)
        send_email_confirmation(request, request.user, signup=False)
    except EmailAddress.DoesNotExist:
        pass

    messages.success(
        request,
        'If that address is awaiting verification, a new confirmation email has been sent.',
    )
    return redirect('account_email_verification_sent')
