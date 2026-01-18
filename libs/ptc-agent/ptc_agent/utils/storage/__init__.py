"""Cloud storage upload utilities.

Supports multiple providers:
- AWS S3
- Cloudflare R2 (zero egress fees)
- Alibaba Cloud OSS
- Disabled mode (none)

Configuration via config.yaml or STORAGE_PROVIDER env var.
"""

from ptc_agent.utils.storage.storage_uploader import (
    delete_object,
    does_object_exist,
    get_provider_id,
    get_provider_name,
    get_public_url,
    get_signed_url,
    is_storage_enabled,
    upload_base64,
    upload_bytes,
    upload_chart,
    upload_file,
    upload_image,
    verify_connection,
)

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
