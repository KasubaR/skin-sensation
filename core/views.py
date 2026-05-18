from django.conf import settings
from django.contrib import messages
from django.core.mail import mail_managers
from django.db.models import Min, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from services.constants import EXCLUDED_SERVICE_SLUGS, service_card_image_url
from services.models import Service, Treatment


def home(request):
    featured_services = (
        Service.objects.filter(is_active=True)
        .annotate(
            min_price=Min('treatments__price', filter=Q(treatments__is_active=True))
        )
        .order_by('sort_order', 'name')[:4]
    )
    for svc in featured_services:
        svc.card_image_url = service_card_image_url(svc.slug)
    return render(
        request,
        'index.html',
        {
            'show_featured_products': False,
            'featured_services': featured_services,
        },
    )


def services(request):
    services_qs = (
        Service.objects.filter(is_active=True)
        .exclude(slug__in=EXCLUDED_SERVICE_SLUGS)
        .annotate(
            min_price=Min(
                'treatments__price',
                filter=Q(treatments__is_active=True),
            ),
        )
        .order_by('sort_order', 'name')
    )
    for service in services_qs:
        service.card_image_url = service_card_image_url(service.slug)
    return render(request, 'services/index.html', {'services': services_qs})


def service_treatments(request, service_slug):
    if service_slug in EXCLUDED_SERVICE_SLUGS:
        raise Http404()
    service = get_object_or_404(Service, slug=service_slug, is_active=True)
    treatments = Treatment.objects.filter(service=service, is_active=True).order_by(
        'sort_order', 'name'
    )
    return render(
        request,
        'services/treatment_list.html',
        {
            'service': service,
            'treatments': treatments,
            'hero_image_url': service_card_image_url(service.slug),
        },
    )


def treatment_detail(request, service_slug, treatment_slug):
    service = get_object_or_404(Service, slug=service_slug, is_active=True)
    treatment = get_object_or_404(
        Treatment,
        slug=treatment_slug,
        service=service,
        is_active=True,
    )
    return render(
        request,
        'services/treatment_detail.html',
        {
            'service': service,
            'treatment': treatment,
        },
    )


def booking(request):
    treatments_qs = (
        Treatment.objects.filter(is_active=True, service__is_active=True)
        .select_related('service')
        .order_by('service__sort_order', 'service__name', 'sort_order', 'name')
    )
    catalog_data = [
        {
            'id': t.pk,
            'name': t.name,
            'price': str(t.price),
            'duration_minutes': t.duration_minutes,
        }
        for t in treatments_qs
    ]
    # Unique ordered categories for filter pills
    seen = set()
    categories = []
    for t in treatments_qs:
        if t.service_id not in seen:
            seen.add(t.service_id)
            categories.append(t.service)
    return render(
        request,
        'booking.html',
        {
            'treatments': treatments_qs,
            'catalog_data': catalog_data,
            'categories': categories,
        },
    )


def gallery(request):
    return render(request, 'gallery.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and subject and message:
            if settings.MANAGERS:
                mail_managers(
                    subject=f'Contact enquiry: {subject}',
                    message=f'From: {name} <{email}>\n\n{message}',
                    fail_silently=False,
                )
            messages.success(request, f"Thank you, {name}! We've received your message and will be in touch soon.")
            return redirect('contact')
        else:
            messages.error(request, "Please fill in all required fields.")

    return render(request, 'contact.html')
