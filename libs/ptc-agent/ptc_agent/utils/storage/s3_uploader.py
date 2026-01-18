"""Standalone AWS S3 Upload Module.

A self-contained module for uploading files to Amazon S3.

Dependencies:
    pip install boto3
    # or: uv add boto3

Environment Variables Required:
    AWS_ACCESS_KEY_ID     - Your AWS Access Key ID
    AWS_SECRET_ACCESS_KEY - Your AWS Secret Access Key
    S3_BUCKET_NAME        - Your S3 bucket name
    S3_REGION             - AWS region (e.g., us-east-1, us-west-2)

Optional Environment Variables:
    S3_PUBLIC_URL_BASE    - Custom domain/CloudFront URL for public access

Usage:
    from s3_uploader import upload_file, upload_base64, get_public_url

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
    All settings are loaded from environment variables.
"""

import base64
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)


class S3Config:
    """S3 Configuration - all settings loaded from environment variables."""

    # AWS S3 Settings (from environment variables)
    REGION = os.getenv("S3_REGION", "us-east-1")
    BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Optional custom domain for public URLs (e.g., CloudFront)
    PUBLIC_URL_BASE = os.getenv("S3_PUBLIC_URL_BASE")

    # Upload constraints
    MAX_UPLOAD_SIZE = int(os.getenv("S3_MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))  # 10MB default

    # Default prefixes for different file types
    DEFAULT_IMAGE_PREFIX = os.getenv("S3_DEFAULT_IMAGE_PREFIX", "images/")
    DEFAULT_CHART_PREFIX = os.getenv("S3_DEFAULT_CHART_PREFIX", "charts/")

    @classmethod
    def get_public_url_base(cls) -> str:
        """Get the public URL base for the bucket.

        Returns custom domain if set, otherwise uses S3 bucket URL.
        Note: Bucket must have public access enabled or use CloudFront.
        """
        if cls.PUBLIC_URL_BASE:
            return cls.PUBLIC_URL_BASE.rstrip("/")
        # Default to S3 bucket URL
        return f"https://{cls.BUCKET_NAME}.s3.{cls.REGION}.amazonaws.com"


def get_s3_client() -> Any:
    """Create and return a configured S3 client using boto3.

    Uses environment variables for authentication:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY

    Returns:
        boto3 S3 client

    Raises:
        ClientError: If client creation fails
    """
    return boto3.client(
        "s3",
        aws_access_key_id=S3Config.ACCESS_KEY_ID,
        aws_secret_access_key=S3Config.SECRET_ACCESS_KEY,
        region_name=S3Config.REGION,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def upload_file(key: str, file_path: str) -> bool:
    """Upload a local file to S3.

    Args:
        key: The object key (path) in S3 bucket (e.g., "images/photo.png")
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
    if file_size > S3Config.MAX_UPLOAD_SIZE:
        logger.error(
            f"File too large: {file_size} bytes > {S3Config.MAX_UPLOAD_SIZE} bytes limit"
        )
        return False

    try:
        client = get_s3_client()

        with path_obj.open("rb") as f:
            client.put_object(
                Bucket=S3Config.BUCKET_NAME,
                Key=key,
                Body=f,
            )

        logger.debug(f"Uploaded {path_obj} to S3 as {key}")
        return True

    except ClientError:
        logger.exception(f"S3 upload failed for {key}")
        return False
    except Exception:
        logger.exception(f"Unexpected error uploading {key}")
        return False


def upload_base64(key: str, image_data: str) -> bool:
    """Upload base64-encoded image data to S3.

    Args:
        key: The object key (path) in S3 bucket
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
    """Upload raw bytes to S3.

    Args:
        key: The object key (path) in S3 bucket
        data: Raw bytes to upload

    Returns:
        bool: True if upload successful, False otherwise

    Example:
        >>> data = b"Hello, World!"
        >>> upload_bytes("text/hello.txt", data)
        True
    """
    if len(data) > S3Config.MAX_UPLOAD_SIZE:
        logger.error(
            f"Data too large: {len(data)} bytes > {S3Config.MAX_UPLOAD_SIZE} bytes limit"
        )
        return False

    try:
        client = get_s3_client()

        client.put_object(
            Bucket=S3Config.BUCKET_NAME,
            Key=key,
            Body=data,
        )

        logger.debug(f"Uploaded bytes to S3 as {key}")
        return True

    except ClientError:
        logger.exception(f"S3 upload failed for {key}")
        return False
    except Exception:
        logger.exception(f"Unexpected error uploading {key}")
        return False


def does_object_exist(key: str) -> bool:
    """Check if an object exists in the S3 bucket.

    Args:
        key: The object key (path) to check

    Returns:
        bool: True if object exists, False otherwise

    Example:
        >>> does_object_exist("images/photo.png")
        True
    """
    try:
        client = get_s3_client()
        client.head_object(
            Bucket=S3Config.BUCKET_NAME,
            Key=key,
        )
        return True

    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            return False
        logger.error(f"Error checking object existence for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking {key}: {e}")
        return False


def delete_object(key: str) -> bool:
    """Delete an object from the S3 bucket.

    Args:
        key: The object key (path) to delete

    Returns:
        bool: True if deletion successful, False otherwise

    Example:
        >>> delete_object("images/old_photo.png")
        True
    """
    try:
        client = get_s3_client()

        client.delete_object(
            Bucket=S3Config.BUCKET_NAME,
            Key=key,
        )

        logger.debug(f"Deleted {key} from S3")
        return True

    except ClientError as e:
        logger.error(f"S3 deletion failed for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting {key}: {e}")
        return False


def get_public_url(key: str) -> str:
    """Get the public URL for an uploaded object.

    Note: This requires either:
    1. Public access enabled on the bucket
    2. A CloudFront distribution (S3_PUBLIC_URL_BASE)

    Args:
        key: The object key (path) in S3 bucket

    Returns:
        str: Public URL to access the object

    Example:
        >>> get_public_url("images/photo.png")
        'https://my-bucket.s3.us-east-1.amazonaws.com/images/photo.png'
    """
    return f"{S3Config.get_public_url_base()}/{key}"


def get_signed_url(key: str, expires_in: int = 3600) -> str | None:
    """Generate a signed URL for temporary access to a private object.

    Args:
        key: The object key (path) in S3 bucket
        expires_in: URL expiration time in seconds (default: 1 hour, max: 7 days)

    Returns:
        str: Signed URL, or None if generation fails

    Example:
        >>> url = get_signed_url("private/document.pdf", expires_in=7200)
        >>> print(url)  # URL valid for 2 hours  # noqa: T201
    """
    try:
        client = get_s3_client()

        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3Config.BUCKET_NAME,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )


    except ClientError as e:
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
        prefix: S3 key prefix (default: S3Config.DEFAULT_IMAGE_PREFIX)
        custom_name: Custom filename (default: original filename with timestamp)

    Returns:
        str: Public URL of uploaded image, or None if upload fails

    Example:
        >>> url = upload_image("/path/to/photo.png")
        >>> print(url)  # noqa: T201
        'https://my-bucket.s3.us-east-1.amazonaws.com/images/photo_20250118_143022.png'

        >>> url = upload_image("/path/to/photo.png", prefix="avatars/", custom_name="user123.png")
        >>> print(url)  # noqa: T201
        'https://my-bucket.s3.us-east-1.amazonaws.com/avatars/user123.png'
    """
    if prefix is None:
        prefix = S3Config.DEFAULT_IMAGE_PREFIX

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
    """Upload a chart/graph image to the charts directory.

    Args:
        file_path: Path to the local chart image
        custom_name: Custom filename (default: original filename with timestamp)

    Returns:
        str: Public URL of uploaded chart, or None if upload fails

    Example:
        >>> url = upload_chart("/path/to/stock_chart.png")
        >>> print(url)  # noqa: T201
        'https://my-bucket.s3.us-east-1.amazonaws.com/charts/stock_chart_20250118_143022.png'
    """
    return upload_image(
        file_path,
        prefix=S3Config.DEFAULT_CHART_PREFIX,
        custom_name=custom_name
    )


def verify_connection() -> bool:
    """Verify S3 connection and credentials.

    Returns:
        bool: True if connection successful, False otherwise

    Example:
        >>> if verify_connection():
        ...     print("S3 connection verified!")  # noqa: T201
        ... else:
        ...     print("Connection failed - check credentials")  # noqa: T201
    """
    try:
        client = get_s3_client()

        # Try to list objects (with max 1) to verify connection
        client.list_objects_v2(
            Bucket=S3Config.BUCKET_NAME,
            MaxKeys=1,
        )

        logger.info(f"Successfully connected to S3 bucket: {S3Config.BUCKET_NAME}")
        return True

    except ClientError as e:
        logger.error(f"S3 connection verification failed: {e}")
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

    print("AWS S3 Uploader - Connection Test")  # noqa: T201
    print("=" * 40)  # noqa: T201
    print(f"Region: {S3Config.REGION}")  # noqa: T201
    print(f"Bucket: {S3Config.BUCKET_NAME}")  # noqa: T201
    print("=" * 40)  # noqa: T201

    # Check environment variables
    missing_vars = []
    if not S3Config.ACCESS_KEY_ID:
        missing_vars.append("AWS_ACCESS_KEY_ID")
    if not S3Config.SECRET_ACCESS_KEY:
        missing_vars.append("AWS_SECRET_ACCESS_KEY")
    if not S3Config.BUCKET_NAME:
        missing_vars.append("S3_BUCKET_NAME")

    if missing_vars:
        print(f"ERROR: Missing environment variables: {', '.join(missing_vars)}")  # noqa: T201
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
