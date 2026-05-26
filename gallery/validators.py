from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_gallery_image(image):
    if image.size > MAX_IMAGE_BYTES:
        raise ValidationError('Image must be under 5 MB.')
    content_type = getattr(image, 'content_type', None)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError('Only JPEG, PNG, or WebP images are allowed.')
