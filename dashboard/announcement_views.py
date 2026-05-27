from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from communications.models import Announcement
from dashboard.activity import log_staff_activity
from dashboard.decorators import staff_required
from dashboard.forms import AnnouncementForm
from dashboard.models import StaffActivityLog


@staff_required
def announcement_list(request):
    announcements = Announcement.objects.order_by('sort_order', '-created_at')
    return render(request, 'dashboard/announcements/list.html', {'announcements': announcements})


@staff_required
def announcement_create(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            log_staff_activity(
                user=request.user,
                action=StaffActivityLog.Action.ANNOUNCEMENT_CREATED,
                target_type='announcement',
                target_id=str(announcement.pk),
                message=f'Announcement created: "{announcement.title}"',
            )
            messages.success(request, 'Announcement created.')
            return redirect('dashboard:announcement_list')
    else:
        form = AnnouncementForm()

    return render(request, 'dashboard/announcements/form.html', {'form': form, 'is_create': True})


@staff_required
def announcement_edit(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        if form.is_valid():
            form.save()
            log_staff_activity(
                user=request.user,
                action=StaffActivityLog.Action.ANNOUNCEMENT_UPDATED,
                target_type='announcement',
                target_id=str(announcement.pk),
                message=f'Announcement updated: "{announcement.title}"',
            )
            messages.success(request, 'Announcement saved.')
            return redirect('dashboard:announcement_list')
    else:
        form = AnnouncementForm(instance=announcement)

    return render(
        request,
        'dashboard/announcements/form.html',
        {'form': form, 'announcement': announcement, 'is_create': False},
    )


@staff_required
@require_POST
def announcement_delete(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    title = announcement.title
    announcement_pk = announcement.pk
    announcement.delete()
    log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.ANNOUNCEMENT_DELETED,
        target_type='announcement',
        target_id=str(announcement_pk),
        message=f'Announcement deleted: "{title}"',
    )
    messages.success(request, 'Announcement deleted.')
    return redirect('dashboard:announcement_list')
