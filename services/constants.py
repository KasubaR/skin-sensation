from django.templatetags.static import static

WAXING_ADDON_SLUGS = ('vajacial', 'eyebrow-tint', 'eyebrow-lamination')

# Service groups hidden from the public /services/ hub (e.g. legacy add-on menu).
EXCLUDED_SERVICE_SLUGS = frozenset({'add-on-treatments', 'addon-treatments'})

# Local card images (700x500) for service hub cards and home page.
_SERVICE_CARD_IMAGES = {
    'nail-treatment':    'images/services/cards/nail-treatment.jpg',
    'massage-therapy':   'images/services/cards/massage-therapy.jpg',
    'facial-treatment':  'images/services/cards/facials.jpg',
    'waxing-treatments': 'images/services/cards/waxing-treatments.jpg',
    'laser-treatments':  'images/services/cards/laser-treatments.jpg',
}

# Local hero images (1440x560) for treatment list page heroes.
_SERVICE_HERO_IMAGES = {
    'nail-treatment':    'images/services/heroes/nail-treatment.jpg',
    'massage-therapy':   'images/services/heroes/massage-therapy.jpg',
    'facial-treatment':  'images/services/heroes/facials.jpg',
    'waxing-treatments': 'images/services/heroes/waxing-treatments.jpg',
    'laser-treatments':  'images/services/heroes/laser-treatments.jpg',
}

_SERVICE_CARD_IMAGE_DEFAULT = 'images/services/cards/facials.jpg'
_SERVICE_HERO_IMAGE_DEFAULT = 'images/services/heroes/facials.jpg'


def service_card_image_url(slug: str) -> str:
    return static(_SERVICE_CARD_IMAGES.get(slug, _SERVICE_CARD_IMAGE_DEFAULT))


def service_hero_image_url(slug: str) -> str:
    return static(_SERVICE_HERO_IMAGES.get(slug, _SERVICE_HERO_IMAGE_DEFAULT))


# Backwards-compatible alias
SERVICE_CARD_IMAGES = _SERVICE_CARD_IMAGES
SERVICE_PLACEHOLDER_IMAGES = _SERVICE_CARD_IMAGES
