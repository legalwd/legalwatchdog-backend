import io
import logging
from typing import Optional

try:
    from minio import Minio
    from minio.error import S3Error

    _HAS_MINIO = True
except Exception as _e:
    Minio = None
    S3Error = Exception
    _HAS_MINIO = False

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
)

logger = logging.getLogger(__name__)

minio_client = None
if _HAS_MINIO:
    try:
        minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    except Exception as e:
        logger.critical(f"Failed to initialize MinIO client: {e}")
        raise StorageConnectionError("Storage service unavailable. Contact administrator.")
else:
    logger.warning(
        "MinIO SDK not installed. Install `minio` package to enable storage operations:"
        "`pip install minio`"
    )


def upload_raw_content(file_data: bytes, bucket_name: str, object_name: str) -> str:
    """Upload raw byte data (HTML/PDF) to MinIO bucket.

    Args:
        file_data (bytes): The raw content to upload.
        bucket_name (str): The target bucket name (environment-specific from config).
        object_name (str): The unique key path (e.g.,
            'raw/jurisdiction_id/source_id/timestamp.html').

    Returns:
        str: The object_name (key) if successful.

    Raises:
        Exception: If upload fails, triggering the Retry/DLQ logic in the caller.
    """
    if not _HAS_MINIO:
        raise Exception(
            "Missing optional dependency: `minio` package is not installed. Run `pip install minio`"
            "to enable storage operations."
        )
    if not minio_client:
        raise StorageConnectionError("Storage service not configured. Contact administrator.")

    try:
        try:
            if not minio_client.bucket_exists(bucket_name=bucket_name):
                logger.info(f"Bucket '{bucket_name}' does not exist. Creating it...")
                minio_client.make_bucket(bucket_name=bucket_name)
        except Exception as e:
            logger.warning(f"Bucket existence check failed (may already exist): {e}")
            try:
                minio_client.make_bucket(bucket_name=bucket_name)
            except Exception as create_err:
                if "BucketAlreadyExists" not in str(
                    create_err
                ) and "BucketAlreadyOwnedByYou" not in str(create_err):
                    raise create_err

        data_stream = io.BytesIO(file_data)

        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data_stream,
            length=len(file_data),
            content_type="application/octet-stream",
        )

        logger.info(f"Successfully uploaded to MinIO: {bucket_name}/{object_name}")
        return object_name

    except S3Error as e:
        logger.error(f"MinIO S3 Error during upload: {e}")
        raise StorageError("Failed to store content. Please try again.")
    except Exception as e:
        logger.error(f"Unexpected error uploading to MinIO: {e}")
        raise StorageError("Failed to store content. Please try again.")


def get_content_from_minio(
    object_name: str, bucket_name: str = "extracted-content", raise_on_error: bool = True
) -> Optional[bytes]:
    """
    Retrieves content from MinIO. Used for debugging,'View Source' features or viewing content.

    Args:
        object_name (str): The object key/path in MinIO
        bucket_name (str): The bucket name (default: 'extracted-content')
        raise_on_error (bool): If True, raises exceptions. If False, returns None on error.

    Returns:
        Optional[bytes]: The content as bytes, None if retrieval fails (when raise_on_error=False)

    Raises:
        S3Error: If object doesn't exist or access denied (when raise_on_error=True)
        Exception: For other errors (when raise_on_error=True)

    Examples:
        # For user downloads (strict error handling)
        content=get_content_from_minio("clean/abc/123.md", "extracted-content", raise_on_error=True)

        # For debugging (lenient, returns None on failure)
        content = get_content_from_minio("raw/abc/123.html", "raw-content", raise_on_error=False)
    """

    if not _HAS_MINIO:
        if raise_on_error:
            raise Exception("Missing optional dependency: `minio` package is not installed.")
        logger.warning("MinIO SDK not installed. Cannot fetch content.")
        return None

    if not minio_client:
        if raise_on_error:
            raise Exception("MinIO client is not initialized. Check configuration.")
        logger.warning("MinIO client not initialized. Cannot fetch content.")
        return None

    try:
        logger.info(f"Fetching from MinIO: {bucket_name}/{object_name}")
        response = minio_client.get_object(bucket_name=bucket_name, object_name=object_name)
        content = response.read()
        response.close()
        response.release_conn()

        logger.info(f"Successfully fetched {len(content)} bytes from {bucket_name}/{object_name}")
        return content

    except S3Error as e:
        logger.error(f"MinIO S3 Error during fetch: {e}")
        if raise_on_error:
            raise StorageNotFoundError("Content not found in storage.")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch object {object_name} from MinIO: {e}")
        if raise_on_error:
            raise StorageError("Failed to retrieve content. Please try again.")
        return None


def upload_profile_picture(
    file_data: bytes, bucket_name: str, object_name: str, content_type: str = "image/jpeg"
) -> str:
    """Upload profile picture data to MinIO bucket.

    Args:
        file_data (bytes): The image data to upload.
        bucket_name (str): The target bucket name (environment-specific from config).
        object_name (str): The unique key path (e.g., 'user_id/uuid.jpg').
        content_type (str): MIME type of the image.

    Returns:
        str: The object_name (key) if successful.

    Raises:
        Exception: If upload fails.
    """
    if not _HAS_MINIO:
        raise Exception(
            "Missing optional dependency: `minio` package is not installed. Run `pip install minio`"
            "to enable storage operations."
        )
    if not minio_client:
        raise Exception("MinIO client is not initialized. Check configuration.")

    try:
        try:
            if not minio_client.bucket_exists(bucket_name=bucket_name):
                logger.info(f"Bucket '{bucket_name}' does not exist. Creating it...")
                minio_client.make_bucket(bucket_name=bucket_name)
        except Exception as e:
            logger.warning(f"Bucket existence check failed (may already exist): {e}")
            try:
                minio_client.make_bucket(bucket_name=bucket_name)
            except Exception as create_err:
                if "BucketAlreadyExists" not in str(
                    create_err
                ) and "BucketAlreadyOwnedByYou" not in str(create_err):
                    raise create_err

        data_stream = io.BytesIO(file_data)

        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data_stream,
            length=len(file_data),
            content_type=content_type,
        )

        logger.info(f"Successfully uploaded profile picture to MinIO: {bucket_name}/{object_name}")
        return object_name

    except S3Error as e:
        logger.error(f"MinIO S3 Error during profile picture upload: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error uploading profile picture to MinIO: {e}")
        raise e
