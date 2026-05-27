from django.core.paginator import Paginator
from django.db.models import Min, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from urllib.parse import urlencode

from services.constants import EXCLUDED_SERVICE_SLUGS, service_card_image_url, service_hero_image_url
from services.models import Service, Treatment
from services.selectors import (
    SORT_CHOICES,
    category_choices,
    featured_treatments,
    filter_services,
    filter_treatments,
)
from gallery.selectors import active_gallery_images, gallery_categories
from testimonials.services import get_featured_testimonials
from communications.models import Announcement

CATALOG_PAGE_SIZE = 12


def _catalog_params(request):
    search = request.GET.get('search', '').strip() or None
    category = request.GET.get('category', '').strip() or None
    sort = request.GET.get('sort', '').strip() or None
    if sort and sort not in SORT_CHOICES:
        sort = None
    page = request.GET.get('page')
    return search, category, sort, page


def _is_browse_mode(search, category, sort, page):
    if search or category:
        return True
    if sort:
        return True
    if page:
        try:
            return int(page) > 1
        except (TypeError, ValueError):
            return True
    return False


def _paginate_treatments(queryset, page_param):
    paginator = Paginator(queryset, CATALOG_PAGE_SIZE)
    page_number = page_param or 1
    try:
        page_number = int(page_number)
    except (TypeError, ValueError):
        page_number = 1
    return paginator.get_page(page_number)


def home(request):
    from django.utils import timezone
    today = timezone.localdate()

    featured_services = (
        Service.objects.filter(is_active=True)
        .annotate(
            min_price=Min('treatments__price', filter=Q(treatments__is_active=True))
        )
        .order_by('sort_order', 'name')[:4]
    )

    announcements = Announcement.objects.filter(
        is_active=True,
    ).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=today),
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=today),
    ).order_by('sort_order', '-created_at')

    return render(
        request,
        'index.html',
        {
            'show_featured_products': False,
            'featured_services': featured_services,
            'featured_testimonials': get_featured_testimonials(),
            'announcements': announcements,
        },
    )


def services(request):
    search, category, sort, page = _catalog_params(request)
    categories = category_choices()
    browse_mode = _is_browse_mode(search, category, sort, page)

    base_params = {k: v for k, v in {'search': search, 'category': category, 'sort': sort}.items() if v}
    context = {
        'search': search or '',
        'category': category or '',
        'sort': sort or '',
        'categories': categories,
        'browse_mode': browse_mode,
        'catalog_url': request.path,
        'show_category_filters': True,
        'base_query': urlencode(base_params),
    }

    if browse_mode:
        treatments_qs = filter_treatments(
            search=search,
            category_slug=category,
            sort=sort,
        )
        context['treatments_page'] = _paginate_treatments(treatments_qs, page)
        context['featured_treatments'] = featured_treatments()
        partial = 'services/partials/treatment_grid.html'
    else:
        context['services'] = filter_services()
        partial = 'services/partials/service_grid.html'

    if request.headers.get('HX-Request'):
        return render(request, partial, context)

    return render(request, 'services/index.html', context)


def service_treatments(request, service_slug):
    if service_slug in EXCLUDED_SERVICE_SLUGS:
        raise Http404()
    service = get_object_or_404(Service, slug=service_slug, is_active=True)
    search, category, sort, page = _catalog_params(request)
    # Per-category page: category param ignored; scope to this service
    treatments_qs = filter_treatments(
        search=search,
        service_slug=service_slug,
        sort=sort,
    )
    treatments_page = _paginate_treatments(treatments_qs, page)

    base_params = {k: v for k, v in {'search': search, 'sort': sort}.items() if v}
    context = {
        'service': service,
        'treatments_page': treatments_page,
        'search': search or '',
        'sort': sort or '',
        'categories': category_choices(),
        'catalog_url': request.path,
        'hero_image_url': service_hero_image_url(service.slug),
        'featured_treatments': featured_treatments(),
        'browse_mode': True,
        'show_category_filters': False,
        'base_query': urlencode(base_params),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'services/partials/treatment_grid.html', context)

    return render(request, 'services/treatment_list.html', context)


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
    catalog_data = list(
        Treatment.objects.filter(is_active=True, service__is_active=True)
        .exclude(service__slug__in=EXCLUDED_SERVICE_SLUGS)
        .order_by('service__sort_order', 'service__name', 'sort_order', 'name')
        .values('id', 'name', 'price', 'duration_minutes', 'service_id', 'service__name')
    )
    for item in catalog_data:
        item['price'] = str(item['price'])

    categories = (
        Service.objects.filter(is_active=True)
        .exclude(slug__in=EXCLUDED_SERVICE_SLUGS)
        .order_by('sort_order', 'name')
    )
    user_email = ''
    if request.user.is_authenticated:
        user_email = request.user.email or ''

    return render(
        request,
        'booking.html',
        {
            'treatments': catalog_data,
            'categories': categories,
            'user_email': user_email,
            'user_is_authenticated': request.user.is_authenticated,
        },
    )


def gallery(request):
    return render(
        request,
        'gallery.html',
        {
            'images': active_gallery_images(),
            'categories': gallery_categories(),
        },
    )


def ratelimit_error(request, exception=None):
    return render(request, '429.html', status=429)
