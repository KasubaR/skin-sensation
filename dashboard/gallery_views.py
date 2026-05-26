from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from dashboard.activity import log_staff_activity
from dashboard.decorators import staff_required
from dashboard.forms import GalleryImageForm
from dashboard.models import StaffActivityLog
from gallery.models import GalleryImage


def _apply_gallery_filters(qs, request):
    category = request.GET.get('category', '').strip()
    if category in GalleryImage.Category.values:
        qs = qs.filter(category=category)

    active = request.GET.get('active', '').strip()
    if active == '1':
        qs = qs.filter(is_active=True)
    elif active == '0':
        qs = qs.filter(is_active=False)

    return qs, category, active


@staff_required
def gallery_list(request):
    qs = GalleryImage.objects.order_by('sort_order', '-created_at')
    qs, category_filter, active_filter = _apply_gallery_filters(qs, request)

    paginator = Paginator(qs, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'dashboard/gallery/list.html',
        {
            'page_obj': page_obj,
            'category_filter': category_filter,
            'active_filter': active_filter,
            'category_choices': GalleryImage.Category.choices,
        },
    )


@staff_required
def gallery_create(request):
    if request.method == 'POST':
        form = GalleryImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save()
            log_staff_activity(
                user=request.user,
                action=StaffActivityLog.Action.GALLERY_CREATED,
                target_type='gallery_image',
                target_id=str(image.pk),
                message=f'Gallery image added: "{image.caption}"',
            )
            messages.success(request, 'Gallery image added.')
            return redirect('dashboard:gallery_list')
    else:
        form = GalleryImageForm()

    return render(
        request,
        'dashboard/gallery/form.html',
        {'form': form, 'is_create': True},
    )


@staff_required
def gallery_edit(request, pk):
    image = get_object_or_404(GalleryImage, pk=pk)

    if request.method == 'POST':
        form = GalleryImageForm(request.POST, request.FILES, instance=image)
        if form.is_valid():
            image = form.save()
            log_staff_activity(
                user=request.user,
                action=StaffActivityLog.Action.GALLERY_UPDATED,
                target_type='gallery_image',
                target_id=str(image.pk),
                message=f'Gallery image updated: "{image.caption}"',
            )
            messages.success(request, 'Gallery image saved.')
            return redirect('dashboard:gallery_list')
    else:
        form = GalleryImageForm(instance=image)

    return render(
        request,
        'dashboard/gallery/form.html',
        {'form': form, 'image': image, 'is_create': False},
    )


@staff_required
@require_POST
def gallery_delete(request, pk):
    image = get_object_or_404(GalleryImage, pk=pk)
    caption = image.caption
    image_pk = image.pk
    image.delete()
    log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.GALLERY_DELETED,
        target_type='gallery_image',
        target_id=str(image_pk),
        message=f'Gallery image deleted: "{caption}"',
    )
    messages.success(request, 'Gallery image deleted.')
    return redirect('dashboard:gallery_list')
