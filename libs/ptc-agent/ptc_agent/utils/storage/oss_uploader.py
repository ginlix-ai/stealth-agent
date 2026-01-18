"""Standalone OSS (Alibaba Cloud Object Storage Service) Upload Module.

A self-contained module for uploading files to Alibaba Cloud OSS.

Dependencies:
    pip install alibabacloud_oss_v2
    # or: uv add alibabacloud_oss_v2

Environment Variables Required:
    OSS_ACCESS_KEY_ID     - Your Alibaba Cloud Access Key ID
    OSS_ACCESS_KEY_SECRET - Your Alibaba Cloud Access Key Secret

Usage:
    from oss_uploader import upload_file, upload_base64, get_public_url

    # Upload a local file
    success = upload_file("images/photo.png", "/path/to/photo.png")
    if success:
        url = get_public_url("images/photo.png")
        print(f"Uploaded to: {url}")  # noqa: T201

    # Upload base64-encoded image
    upload_base64("charts/chart.png", base64_image_data)

    # Upload with auto-generated key
    url = upload_image("/path/to/image.png", prefix="uploads/")

    # Check if file exists
    if does_object_exist("images/photo.png"):
        print("File exists!")  # noqa: T201

    # Delete file
    delete_object("images/photo.png")

Configuration:
    All settings are loaded from environment variables. See OSS_UPLOADER_README.md for details.
"""

import base64
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.exceptions as oss_exceptions

# Configure logging
logger = logging.getLogger(__name__)


class OSSConfig:
    """OSS Configuration - all settings loaded from environment variables."""

    # Alibaba Cloud OSS Settings (from environment variables)
    REGION = os.getenv("OSS_REGION")
    ENDPOINT = os.getenv("OSS_ENDPOINT")
    BUCKET_NAME = os.getenv("OSS_BUCKET_NAME")

    # Upload constraints
    MAX_UPLOAD_SIZE = int(os.getenv("OSS_MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))  # 10MB default

    # Default prefixes for different file types
    DEFAULT_IMAGE_PREFIX = os.getenv("OSS_DEFAULT_IMAGE_PREFIX", "images/")
    DEFAULT_CHART_PREFIX = os.getenv("OSS_DEFAULT_CHART_PREFIX", "charts/")

    @classmethod
    def get_public_url_base(cls) -> str:
        """Get the public URL base for the bucket."""
        return f"https://{cls.BUCKET_NAME}.{cls.ENDPOINT}"


def get_oss_client() -> oss.Client:
    """Create and return a configured OSS client.

    Uses environment variables for authentication:
    - OSS_ACCESS_KEY_ID
    - OSS_ACCESS_KEY_SECRET

    Returns:
        oss.Client: Configured OSS client instance

    Raises:
        oss_exceptions.OSSException: If client creation fails
    """
    cfg = oss.config.load_default()
    cfg.region = OSSConfig.REGION
    cfg.endpoint = OSSConfig.ENDPOINT
    cfg.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

    return oss.Client(cfg)


def upload_file(key: str, file_path: str) -> bool:
    """Upload a local file to OSS.

    Args:
        key: The object key (path) in OSS bucket (e.g., "images/photo.png")
        file_path: Path to the local file to upload

    Returns:
        bool: True if upload successful, False otherwise

    Example:
        >>> upload_file("uploads/document.pdf", "/home/user/document.pdf")
        True
    """
    path_obj = Path(file_path)

    if not path_obj.exists():
        logger.error(f"File not found: {path_obj}")
        return False

    file_size = path_obj.stat().st_size
    if file_size > OSSConfig.MAX_UPLOAD_SIZE:
        logger.error(
            f"File too large: {file_size} bytes > {OSSConfig.MAX_UPLOAD_SIZE} bytes limit"
        )
        return False

    try:
        client = get_oss_client()

        with path_obj.open("rb") as f:
            result = client.put_object(oss.PutObjectRequest(
                bucket=OSSConfig.BUCKET_NAME,
                key=key,
                body=f,
            ))

        logger.debug(f"Uploaded {path_obj} to OSS as {key}, status: {result.status_code}")
        return True

    except oss_exceptions.OssError:
        logger.exception(f"OSS upload failed for {key}")
        return False
    except Exception:
        logger.exception(f"Unexpected error uploading {key}")
        return False


def upload_base64(key: str, image_data: str) -> bool:
    """Upload base64-encoded image data to OSS.

    Args:
        key: The object key (path) in OSS bucket
        image_data: Base64-encoded image string (with or without data URI prefix)

    Returns:
        bool: True if upload successful, False otherwise

    Example:
        >>> import base64
        >>> with open("image.png", "rb") as f:
        ...     b64_data = base64.b64encode(f.read()).decode()
        >>> upload_base64("images/uploaded.png", b64_data)
        True
    """
    try:
        # Remove data URI prefix if present (e.g., "data:image/png;base64,")
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_data)

        return upload_bytes(key, image_bytes)

    except Exception as e:
        logger.error(f"Failed to decode base64 data for {key}: {e}")
        return False


def upload_bytes(key: str, data: bytes) -> bool:
    """Upload raw bytes to OSS.

    Args:
        key: The object key (path) in OSS bucket
        data: Raw bytes to upload

    Returns:
        bool: True if upload successful, False otherwise

    Example:
        >>> data = b"Hello, World!"
        >>> upload_bytes("text/hello.txt", data)
        True
    """
    if len(data) > OSSConfig.MAX_UPLOAD_SIZE:
        logger.error(
            f"Data too large: {len(data)} bytes > {OSSConfig.MAX_UPLOAD_SIZE} bytes limit"
        )
        return False

    try:
        client = get_oss_client()

        result = client.put_object(oss.PutObjectRequest(
            bucket=OSSConfig.BUCKET_NAME,
            key=key,
            body=data,
        ))

        logger.debug(f"Uploaded bytes to OSS as {key}, status: {result.status_code}")
        return True

    except oss_exceptions.OssError:
        logger.exception(f"OSS upload failed for {key}")
        return False
    except Exception:
        logger.exception(f"Unexpected error uploading {key}")
        return False


def does_object_exist(key: str) -> bool:
    """Check if an object exists in the OSS bucket.

    Args:
        key: The object key (path) to check

    Returns:
        bool: True if object exists, False otherwise

    Example:
        >>> does_object_exist("images/photo.png")
        True
    """
    try:
        client = get_oss_client()
        client.head_object(oss.HeadObjectRequest(
            bucket=OSSConfig.BUCKET_NAME,
            key=key,
        ))
        return True

    except oss_exceptions.OssError as e:
        if hasattr(e, "status_code") and e.status_code == 404:
            return False
        logger.error(f"Error checking object existence for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking {key}: {e}")
        return False


def delete_object(key: str) -> bool:
    """Delete an object from the OSS bucket.

    Args:
        key: The object key (path) to delete

    Returns:
        bool: True if deletion successful, False otherwise

    Example:
        >>> delete_object("images/old_photo.png")
        True
    """
    try:
        client = get_oss_client()

        result = client.delete_object(oss.DeleteObjectRequest(
            bucket=OSSConfig.BUCKET_NAME,
            key=key,
        ))

        logger.debug(f"Deleted {key} from OSS, status: {result.status_code}")
        return True

    except oss_exceptions.OssError as e:
        logger.error(f"OSS deletion failed for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting {key}: {e}")
        return False


def get_public_url(key: str) -> str:
    """Get the public URL for an uploaded object.

    Note: This assumes the bucket has public-read ACL.
    For private buckets, use get_signed_url() instead.

    Args:
        key: The object key (path) in OSS bucket

    Returns:
        str: Public URL to access the object

    Example:
        >>> get_public_url("images/photo.png")
        'https://${OSS_BUCKET_NAME}.${OSS_ENDPOINT}/images/photo.png'
    """
    return f"{OSSConfig.get_public_url_base()}/{key}"


def get_signed_url(key: str, expires_in: int = 3600) -> str | None:
    """Generate a signed URL for temporary access to a private object.

    Args:
        key: The object key (path) in OSS bucket
        expires_in: URL expiration time in seconds (default: 1 hour)

    Returns:
        str: Signed URL, or None if generation fails

    Example:
        >>> url = get_signed_url("private/document.pdf", expires_in=7200)
        >>> print(url)  # URL valid for 2 hours  # noqa: T201
    """
    try:
        client = get_oss_client()

        result = client.presign(oss.GetObjectRequest(
            bucket=OSSConfig.BUCKET_NAME,
            key=key,
        ), expires=expires_in)

        return result.url

    except oss_exceptions.OssError as e:
        logger.error(f"Failed to generate signed URL for {key}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating signed URL for {key}: {e}")
        return None


def upload_image(
    file_path: str,
    prefix: str | None = None,
    custom_name: str | None = None
) -> str | None:
    """Upload an image file with auto-generated key and return the public URL.

    Args:
        file_path: Path to the local image file
        prefix: OSS key prefix (default: OSSConfig.DEFAULT_IMAGE_PREFIX)
        custom_name: Custom filename (default: original filename with timestamp)

    Returns:
        str: Public URL of uploaded image, or None if upload fails

    Example:
        >>> url = upload_image("/path/to/photo.png")
        >>> print(url)  # noqa: T201
        'https://${OSS_BUCKET_NAME}.${OSS_ENDPOINT}/images/photo_20250118_143022.png'

        >>> url = upload_image("/path/to/photo.png", prefix="avatars/", custom_name="user123.png")
        >>> print(url)  # noqa: T201
        'https://${OSS_BUCKET_NAME}.${OSS_ENDPOINT}/avatars/user123.png'
    """
    if prefix is None:
        prefix = OSSConfig.DEFAULT_IMAGE_PREFIX

    path_obj = Path(file_path)

    if custom_name:
        filename = custom_name
    else:
        # Add timestamp to avoid collisions
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        stem = path_obj.stem
        suffix = path_obj.suffix
        filename = f"{stem}_{timestamp}{suffix}"

    key = f"{prefix.rstrip('/')}/{filename}"

    if upload_file(key, str(file_path)):
        return get_public_url(key)

    return None


def upload_chart(file_path: str, custom_name: str | None = None) -> str | None:
    """Upload a chart/graph image to the financial_charts directory.

    Args:
        file_path: Path to the local chart image
        custom_name: Custom filename (default: original filename with timestamp)

    Returns:
        str: Public URL of uploaded chart, or None if upload fails

    Example:
        >>> url = upload_chart("/path/to/stock_chart.png")
        >>> print(url)  # noqa: T201
        'https://${OSS_BUCKET_NAME}.${OSS_ENDPOINT}/charts/stock_chart_20250118_143022.png'
    """
    return upload_image(
        file_path,
        prefix=OSSConfig.DEFAULT_CHART_PREFIX,
        custom_name=custom_name
    )


# Convenience function for quick setup verification
def verify_connection() -> bool:
    """Verify OSS connection and credentials.

    Returns:
        bool: True if connection successful, False otherwise

    Example:
        >>> if verify_connection():
        ...     print("OSS connection verified!")  # noqa: T201
        ... else:
        ...     print("Connection failed - check credentials")  # noqa: T201
    """
    try:
        client = get_oss_client()

        # Try to get bucket info to verify connection
        client.get_bucket_info(oss.GetBucketInfoRequest(
            bucket=OSSConfig.BUCKET_NAME,
        ))

        logger.info(f"Successfully connected to OSS bucket: {OSSConfig.BUCKET_NAME}")
        return True

    except oss_exceptions.OssError as e:
        logger.error(f"OSS connection verification failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during connection verification: {e}")
        return False


if __name__ == "__main__":
    # Example usage and connection test
    import sys

    # Set up basic logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("OSS Uploader - Connection Test")  # noqa: T201
    print("=" * 40)  # noqa: T201
    print(f"Region:  {OSSConfig.REGION}")  # noqa: T201
    print(f"Bucket:  {OSSConfig.BUCKET_NAME}")  # noqa: T201
    print(f"Endpoint: {OSSConfig.ENDPOINT}")  # noqa: T201
    print("=" * 40)  # noqa: T201

    # Check environment variables
    if not os.getenv("OSS_ACCESS_KEY_ID"):
        print("ERROR: OSS_ACCESS_KEY_ID environment variable not set")  # noqa: T201
        sys.exit(1)

    if not os.getenv("OSS_ACCESS_KEY_SECRET"):
        print("ERROR: OSS_ACCESS_KEY_SECRET environment variable not set")  # noqa: T201
        sys.exit(1)

    print("Environment variables: OK")  # noqa: T201

    # Test connection
    if verify_connection():
        print("Connection test: PASSED")  # noqa: T201
    else:
        print("Connection test: FAILED")  # noqa: T201
        sys.exit(1)

    print("\nReady to upload files!")  # noqa: T201
    print("\nUsage examples:")  # noqa: T201
    print('  upload_file("images/test.png", "/path/to/test.png")')  # noqa: T201
    print('  url = upload_image("/path/to/image.png")')  # noqa: T201
    print('  url = upload_chart("/path/to/chart.png")')  # noqa: T201
