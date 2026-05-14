"""
Standalone test for image validation logic without full app dependencies.
"""

import io
import sys
from pathlib import Path

from PIL import Image

# Image validation constants
MAX_IMAGES_PER_COMMENT = 5
MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Magic bytes for file type detection
MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',  # JPEG
    b'\x89PNG': 'image/png',  # PNG
    b'RIFF': 'image/webp',  # WebP (RIFF header)
    b'GIF87a': 'image/gif',  # GIF87a
    b'GIF89a': 'image/gif',  # GIF89a
}


class ImageValidationError(Exception):
    """Custom exception for image validation errors."""
    pass


def detect_mime_type(data: bytes) -> str:
    """Detect MIME type by file magic bytes."""
    if len(data) < 4:
        raise ImageValidationError("File is too small to be a valid image")

    # Check magic bytes
    for magic, mime_type in MAGIC_BYTES.items():
        if data.startswith(magic):
            return mime_type

    raise ImageValidationError("Unsupported image format")


def is_valid_image(data: bytes) -> bool:
    """Verify data contains a valid image by opening it."""
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return True
    except Exception:
        return False


def validate_single_image(filename: str, mime_type: str, data: bytes) -> tuple:
    """Validate a single image against all rules."""
    # Check file size
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        return False, "Each image must be 2 MB or less"

    # Detect actual MIME type from magic bytes
    try:
        detected_type = detect_mime_type(data)
    except ImageValidationError as e:
        return False, str(e)

    # Reject GIFs
    if detected_type == 'image/gif':
        return False, "GIFs are not allowed"

    # Check if detected type is allowed
    if detected_type not in ALLOWED_IMAGE_TYPES:
        return False, "Unsupported image format"

    # Verify it's a valid image by opening it
    if not is_valid_image(data):
        return False, "File is not a valid image"

    return True, ""


def create_test_image(format: str = 'JPEG', size_mb: float = 0.5) -> bytes:
    """Create a test image in memory."""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


def create_gif_image() -> bytes:
    """Create a test GIF image."""
    img = Image.new('RGB', (100, 100), color='blue')
    buffer = io.BytesIO()
    img.save(buffer, format='GIF')
    return buffer.getvalue()


def test_all():
    """Run comprehensive image validation tests."""
    tests_passed = 0
    tests_failed = 0

    print("\n" + "="*70)
    print("COMMENT IMAGE UPLOAD VALIDATION TESTS")
    print("="*70)

    # Test 1: Valid JPEG
    print("\n[TEST 1] Valid JPEG image:")
    jpeg_data = create_test_image('JPEG')
    is_valid, error = validate_single_image('test.jpg', 'image/jpeg', jpeg_data)
    if is_valid:
        print("  ✓ PASS - Valid JPEG accepted")
        tests_passed += 1
    else:
        print(f"  ✗ FAIL - Error: {error}")
        tests_failed += 1

    # Test 2: Valid PNG
    print("\n[TEST 2] Valid PNG image:")
    png_data = create_test_image('PNG')
    is_valid, error = validate_single_image('test.png', 'image/png', png_data)
    if is_valid:
        print("  ✓ PASS - Valid PNG accepted")
        tests_passed += 1
    else:
        print(f"  ✗ FAIL - Error: {error}")
        tests_failed += 1

    # Test 3: Valid WebP
    print("\n[TEST 3] Valid WebP image:")
    try:
        webp_data = create_test_image('WEBP')
        is_valid, error = validate_single_image('test.webp', 'image/webp', webp_data)
        if is_valid:
            print("  ✓ PASS - Valid WebP accepted")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Error: {error}")
            tests_failed += 1
    except Exception as e:
        print(f"  ⚠ SKIP - WebP not available: {e}")

    # Test 4: GIF rejected
    print("\n[TEST 4] GIF image (should be REJECTED):")
    gif_data = create_gif_image()
    is_valid, error = validate_single_image('test.gif', 'image/gif', gif_data)
    if not is_valid and 'GIF' in error:
        print(f"  ✓ PASS - GIF correctly rejected: {error}")
        tests_passed += 1
    else:
        print(f"  ✗ FAIL - GIF should be rejected, got: is_valid={is_valid}, error={error}")
        tests_failed += 1

    # Test 5: Oversized image
    print("\n[TEST 5] Oversized image > 2MB (should be REJECTED):")
    large_data = b'\xFF\xD8\xFF' + b'\x00' * (3 * 1024 * 1024)  # 3MB fake JPEG
    is_valid, error = validate_single_image('large.jpg', 'image/jpeg', large_data)
    if not is_valid and '2 MB' in error:
        print(f"  ✓ PASS - Oversized image correctly rejected: {error}")
        tests_passed += 1
    else:
        print(f"  ✗ FAIL - Should reject >2MB, got: is_valid={is_valid}, error={error}")
        tests_failed += 1

    # Test 6: Invalid MIME type
    print("\n[TEST 6] Invalid MIME type image/bmp (should be REJECTED):")
    is_valid, error = validate_single_image('test.bmp', 'image/bmp', b'fake_bmp_data')
    if not is_valid:
        print(f"  ✓ PASS - Invalid format correctly rejected: {error}")
        tests_passed += 1
    else:
        print(f"  ✗ FAIL - Should reject BMP format, got: is_valid={is_valid}")
        tests_failed += 1

    # Test 7: MIME type detection
    print("\n[TEST 7] JPEG magic byte detection:")
    jpeg_data = create_test_image('JPEG')
    try:
        detected = detect_mime_type(jpeg_data)
        if detected == 'image/jpeg':
            print(f"  ✓ PASS - Correctly detected as {detected}")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Expected image/jpeg, got {detected}")
            tests_failed += 1
    except Exception as e:
        print(f"  ✗ FAIL - Detection failed: {e}")
        tests_failed += 1

    # Test 8: PNG magic byte detection
    print("\n[TEST 8] PNG magic byte detection:")
    png_data = create_test_image('PNG')
    try:
        detected = detect_mime_type(png_data)
        if detected == 'image/png':
            print(f"  ✓ PASS - Correctly detected as {detected}")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Expected image/png, got {detected}")
            tests_failed += 1
    except Exception as e:
        print(f"  ✗ FAIL - Detection failed: {e}")
        tests_failed += 1

    # Test 9: GIF magic byte detection
    print("\n[TEST 9] GIF magic byte detection:")
    gif_data = create_gif_image()
    try:
        detected = detect_mime_type(gif_data)
        if detected == 'image/gif':
            print(f"  ✓ PASS - Correctly detected as {detected}")
            tests_passed += 1
        else:
            print(f"  ✗ FAIL - Expected image/gif, got {detected}")
            tests_failed += 1
    except Exception as e:
        print(f"  ✗ FAIL - Detection failed: {e}")
        tests_failed += 1

    # Test 10: Invalid file detection
    print("\n[TEST 10] Invalid file magic bytes (should raise error):")
    try:
        detected = detect_mime_type(b'INVALID_DATA')
        print(f"  ✗ FAIL - Should have raised error, but detected: {detected}")
        tests_failed += 1
    except ImageValidationError as e:
        print(f"  ✓ PASS - Correctly raised error: {e}")
        tests_passed += 1

    # Print summary
    print("\n" + "="*70)
    print(f"TEST SUMMARY: {tests_passed} passed, {tests_failed} failed")
    print("="*70)

    return tests_failed == 0


if __name__ == '__main__':
    success = test_all()
    sys.exit(0 if success else 1)
