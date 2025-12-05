"""
Custom validators for models and forms.
Provides validation for file uploads, prices, and other constraints.
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.translation import gettext_lazy as _


def validate_file_size(file, max_size):
    """
    Validate file size against maximum allowed.

    Args:
        file: UploadedFile object
        max_size: Maximum size in bytes

    Raises:
        ValidationError: If file exceeds max_size
    """
    if file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise ValidationError(
            _(f'File size cannot exceed {max_size_mb}MB. Current size: {file.size / (1024 * 1024):.2f}MB')
        )


def validate_image_size(image):
    """Validate image file size (max 5MB)"""
    max_size = getattr(settings, 'MAX_IMAGE_SIZE', 5 * 1024 * 1024)
    validate_file_size(image, max_size)


def validate_book_file_size(file):
    """Validate book file size (max 50MB)"""
    max_size = getattr(settings, 'MAX_BOOK_FILE_SIZE', 50 * 1024 * 1024)
    validate_file_size(file, max_size)


def validate_course_file_size(file):
    """Validate course file size (max 500MB)"""
    max_size = getattr(settings, 'MAX_COURSE_FILE_SIZE', 500 * 1024 * 1024)
    validate_file_size(file, max_size)


def validate_webinar_file_size(file):
    """Validate webinar file size (max 500MB)"""
    max_size = getattr(settings, 'MAX_WEBINAR_FILE_SIZE', 500 * 1024 * 1024)
    validate_file_size(file, max_size)


def validate_file_extension(file, allowed_extensions):
    """
    Validate file extension against allowed list.

    Args:
        file: UploadedFile object
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.epub'])

    Raises:
        ValidationError: If extension not in allowed list
    """
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            _(f'File extension "{ext}" is not allowed. Allowed extensions: {", ".join(allowed_extensions)}')
        )


def validate_image_extension(image):
    """Validate image file extension"""
    allowed = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.webp'])
    validate_file_extension(image, allowed)


def validate_book_extension(file):
    """Validate book file extension"""
    allowed = getattr(settings, 'ALLOWED_BOOK_EXTENSIONS', ['.pdf', '.epub', '.mobi', '.zip'])
    validate_file_extension(file, allowed)


def validate_course_extension(file):
    """Validate course file extension"""
    allowed = getattr(settings, 'ALLOWED_COURSE_EXTENSIONS', ['.pdf', '.zip', '.mp4'])
    validate_file_extension(file, allowed)


def validate_webinar_extension(file):
    """Validate webinar file extension"""
    allowed = getattr(settings, 'ALLOWED_WEBINAR_EXTENSIONS', ['.pdf', '.zip', '.mp4', '.webm'])
    validate_file_extension(file, allowed)


def validate_positive_price(value):
    """Validate that price is positive"""
    if value <= 0:
        raise ValidationError(_('Price must be greater than 0'))


def validate_rating(value):
    """Validate rating is between 1 and 5"""
    if not (1 <= value <= 5):
        raise ValidationError(_('Rating must be between 1 and 5'))


def validate_image_dimensions(image, max_width=2048, max_height=2048):
    """
    Validate image dimensions.

    Args:
        image: ImageField file
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels

    Raises:
        ValidationError: If dimensions exceed limits
    """
    from PIL import Image

    try:
        img = Image.open(image)
        width, height = img.size

        if width > max_width or height > max_height:
            raise ValidationError(
                _(f'Image dimensions ({width}x{height}) exceed maximum allowed ({max_width}x{max_height})')
            )
    except Exception as e:
        raise ValidationError(_(f'Invalid image file: {str(e)}'))
