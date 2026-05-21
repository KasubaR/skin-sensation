from django.core.cache import cache
from django.db.models import Min, Q

from services.constants import EXCLUDED_SERVICE_SLUGS
from services.models import Service, Treatment

MAX_SEARCH_LEN = 100

SORT_CHOICES = frozenset({
    'price_low',
    'price_high',
    'name',
    'featured',
})


def _active_treatments_base():
    return (
        Treatment.objects.filter(is_active=True, service__is_active=True)
        .exclude(service__slug__in=EXCLUDED_SERVICE_SLUGS)
        .select_related('service')
    )


def apply_sort(queryset, sort: str | None):
    if sort == 'price_low':
        return queryset.order_by('price', 'sort_order', 'name')
    if sort == 'price_high':
        return queryset.order_by('-price', 'sort_order', 'name')
    if sort == 'name':
        return queryset.order_by('name')
    if sort == 'featured':
        return queryset.order_by('-is_featured', 'sort_order', 'name')
    return queryset.order_by(
        'service__sort_order',
        'service__name',
        'subsection',
        'sort_order',
        'name',
    )


def filter_treatments(
    *,
    search: str | None = None,
    category_slug: str | None = None,
    sort: str | None = None,
    service_slug: str | None = None,
):
    """Bookable treatments for public browse and catalog API."""
    qs = _active_treatments_base()

    slug = (category_slug or service_slug or '').strip()
    if slug:
        qs = qs.filter(service__slug=slug)

    term = (search or '').strip()[:MAX_SEARCH_LEN]
    if term:
        qs = qs.filter(
            Q(name__icontains=term) | Q(description__icontains=term)
        )

    if sort and sort in SORT_CHOICES:
        return apply_sort(qs, sort)
    return apply_sort(qs, None)


def filter_services(
    *,
    search: str | None = None,
    category_slug: str | None = None,
):
    """Top-level service groups for the /services/ category hub."""
    qs = (
        Service.objects.filter(is_active=True)
        .exclude(slug__in=EXCLUDED_SERVICE_SLUGS)
        .annotate(
            min_price=Min(
                'treatments__price',
                filter=Q(treatments__is_active=True),
            ),
        )
    )

    slug = (category_slug or '').strip()
    if slug:
        qs = qs.filter(slug=slug)

    term = (search or '').strip()[:MAX_SEARCH_LEN]
    if term:
        qs = qs.filter(
            Q(name__icontains=term)
            | Q(description__icontains=term)
            | Q(tagline__icontains=term)
        )

    return qs.order_by('sort_order', 'name')


def featured_treatments(limit: int = 4):
    key = f'featured_treatments_{limit}'
    result = cache.get(key)
    if result is None:
        result = list(filter_treatments(sort='featured')[:limit])
        cache.set(key, result, timeout=300)
    return result


def category_choices():
    """Active service groups for filter pills."""
    return (
        Service.objects.filter(is_active=True)
        .exclude(slug__in=EXCLUDED_SERVICE_SLUGS)
        .order_by('sort_order', 'name')
    )
