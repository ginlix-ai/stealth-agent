"""Unified Cloud Storage Upload Module.

A unified interface for uploading files to different cloud storage providers.
Supports: AWS S3, Cloudflare R2, Alibaba Cloud OSS, or disabled

Configuration priority:
    1. agent_config.yaml (storage.provider)
    2. STORAGE_PROVIDER environment variable
    3. Default: "s3"

Provider options:
    provider: "s3"    # AWS S3
    provider: "r2"    # Cloudflare R2 (zero egress fees)
    provider: "oss"   # Alibaba Cloud OSS
    provider: "none"  # Disable cloud storage uploads

Usage:
    from storage_uploader import upload_file, upload_bytes, get_public_url, is_storage_enabled

    # Check if storage is enabled
    if is_storage_enabled():
        success = upload_file("images/photo.png", "/path/to/photo.png")
        url = get_public_url("images/photo.png")

Provider Comparison:
    | Provider       | Storage Cost  | Egress        | Best For                    |
    |----------------|---------------|---------------|------------------------------|
    | Cloudflare R2  | $0.015/GB     | FREE          | Public content, US/Global   |
    | AWS S3         | $0.023/GB     | $0.09/GB      | AWS ecosystem, enterprise   |
    | Alibaba OSS    | $0.02/GB      | $0.12/GB      | China market                |
    | none           | N/A           | N/A           | Disable uploads             |
"""

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _load_storage_provider() -> str:
    """Load storage provider from agent_config.yaml, with env var fallback.

    Priority:
        1. agent_config.yaml storage.provider
        2. STORAGE_PROVIDER environment variable
        3. Default: "s3"
    """
    # Try loading from agent_config.yaml first
    config_path = Path(__file__).parent.parent.parent.parent.parent / "agent_config.yaml"
    if config_path.exists():
        try:
            with config_path.open() as f:
                config = yaml.safe_load(f)
            provider = config.get("storage", {}).get("provider")
            if provider:
                logger.debug(f"Storage provider from agent_config.yaml: {provider}")
                return provider.lower()
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f"Failed to load agent_config.yaml: {e}")

    # Fall back to environment variable
    provider = os.getenv("STORAGE_PROVIDER", "s3").lower()
    logger.debug(f"Storage provider from env/default: {provider}")
    return provider


# Load storage provider configuration
STORAGE_PROVIDER = _load_storage_provider()


def is_storage_enabled() -> bool:
    """Check if cloud storage uploads are enabled.

    Returns:
        bool: True if a storage provider is configured, False if STORAGE_PROVIDER=none
    """
    return STORAGE_PROVIDER != "none"


# Import the appropriate module based on provider
if STORAGE_PROVIDER == "none":
    # No-op implementations when storage is disabled
    _PROVIDER_NAME = "Disabled"

    def upload_file(key: str, file_path: str) -> bool:
        """No-op: Storage is disabled."""
        logger.debug("Storage disabled, skipping file upload")
        return False

    def upload_base64(key: str, image_data: str) -> bool:
        """No-op: Storage is disabled."""
        return False

    def upload_bytes(key: str, data: bytes) -> bool:
        """No-op: Storage is disabled."""
        return False

    def does_object_exist(key: str) -> bool:
        """No-op: Storage is disabled."""
        return False

    def delete_object(key: str) -> bool:
        """No-op: Storage is disabled."""
        return False

    def get_public_url(key: str) -> str:
        """No-op: Storage is disabled."""
        return ""

    def get_signed_url(key: str, expires_in: int = 3600) -> str | None:
        """No-op: Storage is disabled."""
        return None

    def upload_image(file_path: str, prefix: str | None = None, custom_name: str | None = None) -> str | None:
        """No-op: Storage is disabled."""
        return None

    def upload_chart(file_path: str, custom_name: str | None = None) -> str | None:
        """No-op: Storage is disabled."""
        return None

    def verify_connection() -> bool:
        """No-op: Storage is disabled."""
        logger.info("Storage is disabled (STORAGE_PROVIDER=none)")
        return True

elif STORAGE_PROVIDER == "s3":
    from ptc_agent.utils.storage.s3_uploader import (
        delete_object,
        does_object_exist,
        get_public_url,
        get_signed_url,
        upload_base64,
        upload_bytes,
        upload_chart,
        upload_file,
        upload_image,
        verify_connection,
    )
    _PROVIDER_NAME = "AWS S3"

elif STORAGE_PROVIDER == "oss":
    from ptc_agent.utils.storage.oss_uploader import (
        delete_object,
        does_object_exist,
        get_public_url,
        get_signed_url,
        upload_base64,
        upload_bytes,
        upload_chart,
        upload_file,
        upload_image,
        verify_connection,
    )
    _PROVIDER_NAME = "Alibaba Cloud OSS"

else:  # Default to R2
    from ptc_agent.utils.storage.r2_uploader import (
        delete_object,
        does_object_exist,
        get_public_url,
        get_signed_url,
        upload_base64,
        upload_bytes,
        upload_chart,
        upload_file,
        upload_image,
        verify_connection,
    )
    _PROVIDER_NAME = "Cloudflare R2"


def get_provider_name() -> str:
    """Get the name of the currently configured storage provider."""
    return _PROVIDER_NAME


def get_provider_id() -> str:
    """Get the ID of the currently configured storage provider."""
    return STORAGE_PROVIDER


# Re-export all functions for convenient import
__all__ = [
    "delete_object",
    "does_object_exist",
    "get_provider_id",
    "get_provider_name",
    "get_public_url",
    "get_signed_url",
    "is_storage_enabled",
    "upload_base64",
    "upload_bytes",
    "upload_chart",
    "upload_file",
    "upload_image",
    "verify_connection",
]


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("Unified Storage Uploader - Connection Test")  # noqa: T201
    print("=" * 50)  # noqa: T201
    print(f"Provider: {get_provider_name()} ({get_provider_id()})")  # noqa: T201
    print("=" * 50)  # noqa: T201

    # Test connection
    if verify_connection():
        print("Connection test: PASSED")  # noqa: T201
    else:
        print("Connection test: FAILED")  # noqa: T201
        sys.exit(1)

    print("\nReady to upload files!")  # noqa: T201
    print("\nTo switch providers, edit agent_config.yaml:")  # noqa: T201
    print("  storage:")  # noqa: T201
    print("    provider: s3    # AWS S3")  # noqa: T201
    print("    provider: r2    # Cloudflare R2 (zero egress)")  # noqa: T201
    print("    provider: oss   # Alibaba Cloud OSS")  # noqa: T201
    print("    provider: none  # Disable uploads")  # noqa: T201
    print("\nOr set STORAGE_PROVIDER environment variable as override.")  # noqa: T201
