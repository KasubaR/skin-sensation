from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from dashboard.activity import log_staff_activity
from dashboard.decorators import staff_required
from dashboard.models import StaffActivityLog
from testimonials.models import Testimonial
from testimonials.selectors import FEATURED_LIMIT
from testimonials.services import (
    approve_review,
    delete_review,
    feature_review,
    reject_review,
)


def _apply_list_filters(qs, request):
    status = request.GET.get('status', '').strip()
    if status in Testimonial.Status.values:
        qs = qs.filter(status=status)

    if request.GET.get('featured') == '1':
        qs = qs.filter(is_featured=True)

    rating_lte = request.GET.get('rating_lte', '').strip()
    if rating_lte.isdigit():
        qs = qs.filter(rating__lte=int(rating_lte))

    if request.GET.get('recent') == '1':
        qs = qs.order_by('-created_at')

    return qs, status


@staff_required
def testimonial_list(request):
    qs = Testimonial.objects.select_related('customer', 'service').order_by('-created_at')
    qs, status_filter = _apply_list_filters(qs, request)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    featured_count = Testimonial.objects.filter(
        status=Testimonial.Status.APPROVED,
        is_featured=True,
    ).count()

    return render(
        request,
        'dashboard/testimonials/list.html',
        {
            'page_obj': page_obj,
            'status_filter': status_filter,
            'status_choices': Testimonial.Status.choices,
            'featured_count': featured_count,
            'featured_limit': FEATURED_LIMIT,
        },
    )


@staff_required
def testimonial_detail(request, pk):
    testimonial = get_object_or_404(
        Testimonial.objects.select_related('customer', 'service'),
        pk=pk,
    )
    featured_count = Testimonial.objects.filter(
        status=Testimonial.Status.APPROVED,
        is_featured=True,
    ).count()

    return render(
        request,
        'dashboard/testimonials/detail.html',
        {
            'testimonial': testimonial,
            'featured_count': featured_count,
            'featured_limit': FEATURED_LIMIT,
        },
    )


@staff_required
@require_POST
def testimonial_approve(request, pk):
    testimonial = get_object_or_404(Testimonial, pk=pk)
    approve_review(testimonial)
    log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.REVIEW_APPROVED,
        target_type='testimonial',
        target_id=str(pk),
        message=f'Approved review #{pk}',
    )
    messages.success(request, 'Review approved.')
    return redirect('dashboard:testimonial_detail', pk=pk)


@staff_required
@require_POST
def testimonial_reject(request, pk):
    testimonial = get_object_or_404(Testimonial, pk=pk)
    reject_review(testimonial)
    log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.REVIEW_REJECTED,
        target_type='testimonial',
        target_id=str(pk),
        message=f'Rejected review #{pk}',
    )
    messages.success(request, 'Review rejected.')
    return redirect('dashboard:testimonial_detail', pk=pk)


@staff_required
@require_POST
def testimonial_feature(request, pk):
    testimonial = get_object_or_404(Testimonial, pk=pk)
    featured = request.POST.get('featured', '1') == '1'
    try:
        feature_review(testimonial, featured=featured)
        label = 'featured' if featured else 'unfeatured'
        log_staff_activity(
            user=request.user,
            action=StaffActivityLog.Action.REVIEW_FEATURED,
            target_type='testimonial',
            target_id=str(pk),
            message=f'Review #{pk} {label} on homepage',
        )
        messages.success(request, f'Review {label} on homepage.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('dashboard:testimonial_detail', pk=pk)


@staff_required
@require_POST
def testimonial_delete(request, pk):
    testimonial = get_object_or_404(Testimonial, pk=pk)
    delete_review(testimonial)
    log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.REVIEW_DELETED,
        target_type='testimonial',
        target_id=str(pk),
        message=f'Deleted review #{pk}',
    )
    messages.success(request, 'Review deleted.')
    return redirect('dashboard:testimonial_list')
