from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from services.models import Service
from testimonials.forms import TestimonialForm
from testimonials.models import Testimonial
from testimonials.selectors import approved_for_public_list
from testimonials.services import get_reviewable_services


def testimonial_list(request):
    service_slug = request.GET.get('service', '').strip()
    qs = approved_for_public_list(service_slug=service_slug or None)
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    services_with_reviews = (
        Service.objects.filter(
            is_active=True,
            testimonials__status=Testimonial.Status.APPROVED,
        )
        .distinct()
        .order_by('sort_order', 'name')
    )

    return render(
        request,
        'testimonials/list.html',
        {
            'page_obj': page_obj,
            'service_filter': service_slug,
            'services_with_reviews': services_with_reviews,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
@ratelimit(key='user', rate='5/h', method='POST', block=True)
def review_create(request):
    initial = {}
    service_slug = request.GET.get('service', '').strip()
    if service_slug:
        service = Service.objects.filter(slug=service_slug, is_active=True).first()
        if service and get_reviewable_services(request.user).filter(pk=service.pk).exists():
            initial['service'] = service

    if request.method == 'POST':
        form = TestimonialForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Review submitted for approval.')
                return redirect('review_list')
            except ValidationError as e:
                form.add_error(None, e)
    else:
        reviewable = get_reviewable_services(request.user)
        if not reviewable.exists():
            messages.info(
                request,
                'You have no services left to review. Reviews require a completed appointment.',
            )
        form = TestimonialForm(user=request.user, initial=initial)

    return render(
        request,
        'testimonials/create.html',
        {'form': form},
    )
