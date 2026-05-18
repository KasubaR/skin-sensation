WAXING_ADDON_SLUGS = ('vajacial', 'eyebrow-tint', 'eyebrow-lamination')

# Service groups hidden from the public /services/ hub (e.g. legacy add-on menu).
EXCLUDED_SERVICE_SLUGS = frozenset({'add-on-treatments', 'addon-treatments'})

# Unsplash hero images for service hub cards (w=700, crop, q=80).
SERVICE_CARD_IMAGES = {
    'nail-treatment': (
        'https://images.unsplash.com/photo-1604654894610-df63bc536371'
        '?auto=format&fit=crop&w=700&h=468&q=80'
    ),
    'massage-therapy': (
        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874'
        '?auto=format&fit=crop&w=700&h=468&q=80'
    ),
    'facial-treatment': (
        'https://images.unsplash.com/photo-1515377905703-c4788e51af15'
        '?auto=format&fit=crop&w=700&h=468&q=80'
    ),
    'waxing-treatments': (
        'https://images.unsplash.com/photo-1560750588-73207b1ef5b8'
        '?auto=format&fit=crop&w=700&h=468&q=80'
    ),
    'laser-treatments': (
        'https://images.unsplash.com/photo-1616394584738-fc6e612e71b9'
        '?auto=format&fit=crop&w=700&h=468&q=80'
    ),
}

SERVICE_CARD_IMAGE_DEFAULT = (
    'https://images.unsplash.com/photo-1540555700478-4be289fbecef'
    '?auto=format&fit=crop&w=700&h=468&q=80'
)


def service_card_image_url(slug: str) -> str:
    return SERVICE_CARD_IMAGES.get(slug, SERVICE_CARD_IMAGE_DEFAULT)


# Backwards-compatible alias
SERVICE_PLACEHOLDER_IMAGES = SERVICE_CARD_IMAGES
