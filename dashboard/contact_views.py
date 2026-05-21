from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from communications.models import BusinessInformation, ContactMessage
from dashboard.activity import log_staff_activity
from dashboard.decorators import staff_required
from dashboard.forms import BusinessSettingsForm, ContactMessageStatusForm
from dashboard.models import StaffActivityLog


@staff_required
def contact_message_list(request):
    status = request.GET.get('status', '').strip()
    qs = ContactMessage.objects.all()
    if status in ContactMessage.Status.values:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'dashboard/contact_messages/list.html',
        {
            'page_obj': page_obj,
            'status_filter': status,
            'status_choices': ContactMessage.Status.choices,
        },
    )


@staff_required
def contact_message_detail(request, pk):
    contact_message = get_object_or_404(ContactMessage, pk=pk)

    if request.method == 'POST':
        form = ContactMessageStatusForm(request.POST, instance=contact_message)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            form.save()
            log_staff_activity(
                user=request.user,
                action=StaffActivityLog.Action.CONTACT_MESSAGE_STATUS,
                target_type='contact_message',
                target_id=str(pk),
                message=f'Set contact message #{pk} status to {new_status}',
            )
            messages.success(request, 'Message status updated.')
            return redirect('dashboard:contact_message_detail', pk=pk)
    else:
        if contact_message.status == ContactMessage.Status.NEW:
            ContactMessage.objects.filter(
                pk=contact_message.pk,
                status=ContactMessage.Status.NEW,
            ).update(status=ContactMessage.Status.READ)
            contact_message.status = ContactMessage.Status.READ
        form = ContactMessageStatusForm(instance=contact_message)

    return render(
        request,
        'dashboard/contact_messages/detail.html',
        {
            'contact_message': contact_message,
            'form': form,
        },
    )


@staff_required
@require_POST
def contact_message_delete(request, pk):
    contact_message = get_object_or_404(ContactMessage, pk=pk)
    contact_message.delete()
    log_staff_activity(
        user=request.user,
        action=StaffActivityLog.Action.CONTACT_MESSAGE_DELETED,
        target_type='contact_message',
        target_id=str(pk),
        message=f'Deleted contact message #{pk}',
    )
    messages.success(request, 'Message deleted.')
    return redirect('dashboard:contact_message_list')


@staff_required
def business_settings_edit(request):
    business = BusinessInformation.load()

    if request.method == 'POST':
        form = BusinessSettingsForm(request.POST, instance=business)
        if form.is_valid():
            form.save()
            messages.success(request, 'Business settings saved.')
            return redirect('dashboard:business_settings')
    else:
        form = BusinessSettingsForm(instance=business)

    return render(
        request,
        'dashboard/business_settings/form.html',
        {'form': form, 'business': business},
    )
