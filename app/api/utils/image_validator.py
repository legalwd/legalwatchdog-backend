"""
Image validation utility for image uploads.

Enforces strict validation rules:
- Maximum 5 images per comment/upload
- Maximum 2MB per image
- Only JPEG, PNG, WebP formats
- No GIFs
- Verifies actual file content (magic bytes)
- Strips EXIF metadata

Can be used across the application for any image upload feature.
"""

import io
import logging
from typing import List, Tuple

from app.api.core.custom_exceptions.exceptions import (
    GifNotAllowedError,
    ImageTooLargeError,
    ImageValidationError,
    InvalidImageFormatError,
    TooManyImagesError,
)

try:
    from PIL import Image
except ImportError:
    raise ImportError("Pillow is required for image validation. Install with: pip install Pillow")

logger = logging.getLogger("app")

# Image validation constants
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB
MAX_IMAGES = 5

# Magic bytes for file type detection
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",  # JPEG
    b"\x89PNG": "image/png",  # PNG
    b"RIFF": "image/webp",  # WebP (RIFF header)
    b"GIF87a": "image/gif",  # GIF87a
    b"GIF89a": "image/gif",  # GIF89a
}


def detect_mime_type(data: bytes) -> str:
    """
    Detect MIME type by file magic bytes.

    Args:
        data: Raw image data

    Returns:
        Detected MIME type

    Raises:
        InvalidImageFormatError: If file type cannot be detected
    """
    if len(data) < 4:
        raise InvalidImageFormatError("File is too small to be a valid image")

    # Check magic bytes
    for magic, mime_type in MAGIC_BYTES.items():
        if data.startswith(magic):
            return mime_type

    raise InvalidImageFormatError()


def is_valid_image(data: bytes) -> bool:
    """
    Verify data contains a valid image by opening it.

    Args:
        data: Raw image data

    Returns:
        True if valid image, False otherwise
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return True
    except Exception:
        return False


def strip_exif_metadata(data: bytes) -> bytes:
    """
    Strip EXIF and other metadata from image data.

    Args:
        data: Raw image data with potential metadata

    Returns:
        Image data without metadata

    Raises:
        ImageValidationError: If image cannot be processed
    """
    try:
        img = Image.open(io.BytesIO(data))

        # Create new image without EXIF data
        # Convert RGBA to RGB if necessary for JPEG
        if img.format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background

        # Save image without EXIF
        output = io.BytesIO()
        # Save as the original format without exif
        save_kwargs = {}
        if img.format == "JPEG":
            save_kwargs["quality"] = 95
        img.save(output, format=img.format or "JPEG", **save_kwargs)

        return output.getvalue()

    except Exception as e:
        logger.exception(f"Error stripping EXIF metadata: {str(e)}")
        raise ImageValidationError("Failed to process image")


def validate_single_image(filename: str, data: bytes) -> Tuple[bool, str, dict]:
    """
    Validate a single image against all rules and derive metadata.

    Backend derives all metadata from actual file content:
    - Size is calculated from data length
    - MIME type is detected from magic bytes
    - No trust in client-provided metadata

    Args:
        filename: Original filename for display purposes
        data: Raw image data

    Returns:
        Tuple of (is_valid, error_message, metadata_dict)
        metadata_dict contains: {"size": int, "mime_type": str} if valid
    """
    # Derive actual file size from data
    actual_size = len(data)

    # Check file size
    if actual_size > MAX_IMAGE_SIZE:
        return False, ImageTooLargeError().message, {}

    # Detect actual MIME type from magic bytes (not trusting client)
    try:
        detected_mime_type = detect_mime_type(data)
    except InvalidImageFormatError as e:
        return False, e.message, {}

    # Reject GIFs
    if detected_mime_type == "image/gif":
        return False, GifNotAllowedError().message, {}

    # Check if detected type is allowed
    if detected_mime_type not in ALLOWED_MIME_TYPES:
        return False, InvalidImageFormatError().message, {}

    # Verify it's a valid image by opening it
    if not is_valid_image(data):
        return False, ImageValidationError("File is not a valid image").message, {}

    # Return derived metadata
    metadata = {
        "size": actual_size,
        "mime_type": detected_mime_type,
    }

    return True, "", metadata


def validate_images(images: List) -> Tuple[bool, List[str], List]:
    """
    Validate all images in a batch and derive metadata from actual content.

    Backend derives all metadata (size, MIME type) from file content.
    Does not trust client-provided metadata.

    Args:
        images: List of dicts with {"filename": str, "data": bytes}
               OR List of UploadFile objects from FastAPI

    Returns:
        Tuple of (is_valid, error_messages, processed_images)
        processed_images contains: [{"filename": str, "mime_type": str, "data": bytes, "size": int}]
    """
    if not images:
        return True, [], []

    # Check max image count
    if len(images) > MAX_IMAGES:
        return False, [TooManyImagesError().message], []

    errors = []
    processed_images = []

    for idx, image in enumerate(images):
        # Extract filename and data (support both dict and UploadFile)
        if hasattr(image, "filename"):
            # UploadFile object
            filename = image.filename
            data = image.get("data") if isinstance(image, dict) else image.data
        else:
            # Dict format
            filename = image.get("filename", f"image_{idx + 1}")
            data = image.get("data", b"")

        # Validate individual image and get derived metadata
        is_valid, error, metadata = validate_single_image(
            filename=filename,
            data=data,
        )

        if not is_valid:
            errors.append(f"Image {idx + 1} ({filename}): {error}")
            continue

        # Strip EXIF metadata
        try:
            cleaned_data = strip_exif_metadata(data)
        except ImageValidationError as e:
            errors.append(f"Image {idx + 1} ({filename}): {e.message}")
            continue

        # Use derived metadata from validation (backend-calculated)
        processed_images.append(
            {
                "filename": filename,
                "mime_type": metadata["mime_type"],  # Backend-detected from magic bytes
                "data": cleaned_data,
                "size": len(cleaned_data),  # Backend-calculated actual size after EXIF strip
            }
        )

    if errors:
        return False, errors, []

    return True, [], processed_images
