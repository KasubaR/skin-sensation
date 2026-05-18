from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.services.dashboard import get_dashboard_context


@login_required
@require_GET
def portal_dashboard(request):
    ctx = get_dashboard_context(request.user)
    ctx['portal_nav'] = 'dashboard'
    return render(request, 'accounts/portal/dashboard.html', ctx)
