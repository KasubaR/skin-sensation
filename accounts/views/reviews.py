from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from testimonials.models import Testimonial


@login_required
@require_GET
def review_list(request):
    reviews = (
        Testimonial.objects.filter(customer=request.user)
        .select_related('service')
        .order_by('-created_at')
    )
    return render(
        request,
        'accounts/portal/reviews/list.html',
        {
            'reviews': reviews,
            'portal_nav': 'reviews',
        },
    )


@login_required
@require_GET
def review_create_redirect(request):
    return redirect('review_create')
