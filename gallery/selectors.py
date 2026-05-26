from gallery.models import GalleryImage


def active_gallery_images():
    return GalleryImage.objects.filter(is_active=True).order_by('sort_order', '-created_at')


def gallery_categories():
    """Category choices that have at least one active image."""
    used = (
        GalleryImage.objects.filter(is_active=True)
        .values_list('category', flat=True)
        .distinct()
    )
    used_set = set(used)
    return [
        (value, label)
        for value, label in GalleryImage.Category.choices
        if value in used_set
    ]
