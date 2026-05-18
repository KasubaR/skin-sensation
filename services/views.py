import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Treatment

MAX_TREATMENTS = 200


def _treatment_image_url(request, treatment):
    if treatment.image:
        return request.build_absolute_uri(treatment.image.url)
    return None


@require_GET
def service_list(request):
    """JSON catalog of bookable treatments. service_ids in booking APIs are treatment PKs."""
    treatments = (
        Treatment.objects.filter(is_active=True)
        .select_related('service')
        .order_by('service__sort_order', 'service__name', 'sort_order', 'name')
    )
    service_slug = request.GET.get('service', '').strip()
    if service_slug:
        treatments = treatments.filter(service__slug=service_slug)
    treatments = treatments[:MAX_TREATMENTS]
    payload = [
        {
            'id': treatment.pk,
            'slug': treatment.slug,
            'name': treatment.name,
            'price': str(treatment.price),
            'duration_minutes': treatment.duration_minutes,
            'service': treatment.service.name,
            'service_slug': treatment.service.slug,
            'image_url': _treatment_image_url(request, treatment),
        }
        for treatment in treatments
    ]
    return JsonResponse(payload, safe=False)
