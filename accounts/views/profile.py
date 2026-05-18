from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.forms import NotificationPreferencesForm, ProfileEditForm
from accounts.models import CustomerProfile


def _get_profile(user) -> CustomerProfile:
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    return profile


@login_required
@require_GET
def profile_detail(request):
    profile = _get_profile(request.user)
    return render(
        request,
        'accounts/portal/profile/detail.html',
        {'profile': profile, 'portal_nav': 'profile'},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def profile_edit(request):
    profile = _get_profile(request.user)
    form = ProfileEditForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        user=request.user,
    )
    notif_form = NotificationPreferencesForm(
        request.POST or None,
        profile=profile,
        prefix='notif',
    )

    if request.method == 'POST':
        if form.is_valid() and notif_form.is_valid():
            form.save()
            profile.notification_preferences = notif_form.to_preferences()
            profile.save(update_fields=['notification_preferences'])
            messages.success(request, 'Your profile has been updated.')
            return redirect('profile_detail')

    return render(
        request,
        'accounts/portal/profile/edit.html',
        {
            'profile': profile,
            'form': form,
            'notif_form': notif_form,
            'portal_nav': 'profile',
        },
    )


@login_required
@require_GET
def profile_password(request):
    return render(
        request,
        'accounts/portal/profile/password.html',
        {'portal_nav': 'profile'},
    )
