from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from services.selectors import MAX_SEARCH_LEN, filter_treatments

MAX_TREATMENTS = 200


def _treatment_image_url(request, treatment):
    if treatment.image:
        return request.build_absolute_uri(treatment.image.url)
    return None


@cache_page(300)
@ratelimit(key='ip', rate='60/m', block=True)
@require_GET
def service_list(request):
    """JSON catalog of bookable treatments. service_ids in booking APIs are treatment PKs."""
    service_slug = request.GET.get('service', '').strip() or None
    search = request.GET.get('search', '').strip()[:MAX_SEARCH_LEN] or None
    treatments = filter_treatments(
        search=search,
        category_slug=service_slug,
    ).only(
        'id', 'slug', 'name', 'price', 'duration_minutes', 'image',
        'service__name', 'service__slug',
    )[:MAX_TREATMENTS]
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
