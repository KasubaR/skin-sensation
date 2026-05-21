from django.core.cache import cache

from communications.models import BusinessInformation


def business_info(request):
    business = cache.get('business_info')
    if business is None:
        business = BusinessInformation.load()
        cache.set('business_info', business, timeout=3600)
    return {'business': business}
