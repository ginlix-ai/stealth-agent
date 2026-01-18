"""Self-contained View Image Middleware for Vision LLMs.

This module provides a complete solution for injecting images into LLM conversations
as HumanMessage content blocks, enabling vision-capable models to process images
even when the underlying API doesn't support images in tool messages.

Architecture:
- Tool: `view_image` accepts URLs and/or base64 encoded images
- Middleware: Intercepts tool result and injects images as HumanMessage
- Uses LangGraph's Command pattern to update message history

Usage:
    from view_image_middleware import view_image, ViewImageMiddleware

    # Create agent with the middleware
    middleware = [ViewImageMiddleware(validate_urls=True)]
    agent = create_agent(model=model, tools=[view_image], middleware=middleware)

    # Agent can then call view_image to load images for vision analysis

Dependencies:
    httpx[http2]>=0.24.0
    Pillow>=9.0.0
"""

import asyncio
import base64
import io
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.types import Command
from PIL import Image

logger = logging.getLogger(__name__)


def _validate_list_arg(value: Any, param_name: str) -> str | None:
    """Validate that a tool argument is a list, not a string.

    Args:
        value: The value to validate.
        param_name: Name of the parameter for error messages.

    Returns:
        Error message if invalid, None if valid.
    """
    if value is None or isinstance(value, list):
        return None
    if isinstance(value, str):
        return (
            f"Invalid type for '{param_name}': expected a list, got a string. "
            f'Pass an actual list like {param_name}=["path1.png", "path2.png"], '
            f"not a string like {param_name}='[...]'."
        )
    return f"Invalid type for '{param_name}': expected a list, got {type(value).__name__}."


# =============================================================================
# Image Validation Constants and Functions
# =============================================================================

# OpenAI Vision API supported image formats
# Reference: https://platform.openai.com/docs/guides/vision
OPENAI_SUPPORTED_FORMATS = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


async def _check_url_accessible_quick(url: str, timeout: int) -> bool:
    """Lenient validation: Quick HEAD request to check if image exists.

    Uses HEAD request (doesn't download) for fast accessibility check.
    Suitable for images that will only be displayed in frontend, not sent to Vision APIs.

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        True if accessible with image content type, False otherwise
    """
    try:
        async with httpx.AsyncClient(http2=True, timeout=float(timeout)) as client:
            response = await client.head(url, follow_redirects=True)
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "").lower()
                # For lenient mode, accept any image/* content type
                return content_type.startswith("image/")
            logger.debug(
                f"HEAD request failed with status {response.status_code} for {url}"
            )
            return False
    except httpx.TimeoutException:
        logger.debug(f"Timeout during HEAD request for {url}")
        return False
    except (httpx.RequestError, OSError) as e:
        logger.debug(f"HEAD request error for {url}: {type(e).__name__}: {e}")
        return False


async def _check_url_downloadable(url: str, timeout: int, *, retry: bool = True) -> bool:
    """Strict validation: Full GET request with image decoding validation.

    Uses GET request to download and decode the image, matching what OpenAI's Vision API
    will do. This catches:
    - Slow-downloading images that would timeout on OpenAI
    - Corrupted images that can't be decoded
    - Unsupported image formats
    - Images with incorrect Content-Type headers

    Args:
        url: URL to check
        timeout: Request timeout in seconds
        retry: Whether to retry once on timeout/connection errors (default: True)

    Returns:
        True if accessible, downloadable, decodable and has supported format, False otherwise
    """

    async def _attempt_validation() -> bool:
        """Single validation attempt."""
        try:
            async with httpx.AsyncClient(http2=True, timeout=float(timeout)) as client:
                response = await client.get(url, follow_redirects=True)

                if response.status_code != 200:
                    logger.debug(
                        f"GET request failed with status {response.status_code} for {url}"
                    )
                    return False

                # Strict Content-Type validation: Only OpenAI-supported formats
                content_type = (
                    response.headers.get("Content-Type", "")
                    .lower()
                    .split(";")[0]
                    .strip()
                )
                if content_type not in OPENAI_SUPPORTED_FORMATS:
                    logger.debug(
                        f"Unsupported Content-Type '{content_type}' for {url}. "
                        f"OpenAI only supports: {sorted(OPENAI_SUPPORTED_FORMATS)}"
                    )
                    return False

                # Get the image data
                image_data = response.content

                if not image_data:
                    logger.debug(f"Empty image data received from {url}")
                    return False

                # Verify the image is decodable with PIL
                try:
                    img = Image.open(io.BytesIO(image_data))
                    # Verify the image by attempting to load it
                    img.verify()
                    logger.debug(
                        f"Image validation success: {url} "
                        f"(format={img.format}, size={img.size}, {len(image_data)} bytes)"
                    )
                    return True
                except (OSError, ValueError) as e:  # PIL/image decoding errors
                    logger.debug(
                        f"Image decoding failed for {url}: {type(e).__name__}: {e}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.debug(f"Timeout ({timeout}s) downloading image from {url}")
            return False
        except httpx.RequestError as e:
            logger.debug(f"Network error downloading {url}: {type(e).__name__}: {e}")
            return False
        except OSError as e:  # Catch network/IO errors
            logger.debug(f"Unexpected error validating {url}: {type(e).__name__}: {e}")
            return False

    # First attempt
    result = await _attempt_validation()

    # Retry once on failure if enabled (helps with intermittent CDN issues)
    if not result and retry:
        logger.debug(f"Retrying validation for {url}")
        await asyncio.sleep(0.5)  # Brief delay before retry
        result = await _attempt_validation()
        if result:
            logger.debug(f"Image validation succeeded on retry: {url}")

    return result


async def validate_image_url(
    url: str, timeout: int | None = None, *, strict: bool = True
) -> str | None:
    """Validate image URL and auto-upgrade HTTP to HTTPS when possible.

    Supports two validation modes:
    - Strict mode (default): Uses GET request with full image download and decoding validation
      -> For images sent to OpenAI Vision API or other services with strict requirements
      -> Validates Content-Type is one of OpenAI's supported formats
      -> Actually decodes the image with PIL to ensure it's valid
      -> Default 2s timeout to match OpenAI's behavior
      -> Includes retry logic for intermittent CDN failures

    - Lenient mode: Uses HEAD request for quick accessibility check
      -> For images only displayed in frontend (not sent to Vision APIs)
      -> Faster validation, doesn't test download speed or decode image
      -> Default 10s timeout for slower CDNs

    For HTTP URLs, automatically attempts to upgrade to HTTPS for compatibility.

    Args:
        url: Image URL to validate
        timeout: Request timeout in seconds (default: 2 for strict, 10 for lenient)
        strict: If True, use GET with full validation; if False, use HEAD (default: True)

    Returns:
        The validated URL (potentially upgraded to HTTPS) if valid, None otherwise

    Examples:
        >>> # Strict mode (for OpenAI Vision API) - 2s timeout, full validation
        >>> validated_url = await validate_image_url("http://example.com/image.jpg")
        >>>
        >>> # Lenient mode (for frontend display) - 10s timeout, quick check
        >>> validated_url = await validate_image_url("http://example.com/image.jpg",
        ...                                           strict=False)
        >>>
        >>> # Custom timeout
        >>> validated_url = await validate_image_url("http://example.com/image.jpg",
        ...                                           timeout=5, strict=True)
    """
    # Set default timeouts based on mode
    if timeout is None:
        timeout = 2 if strict else 10
    # Select appropriate validation function based on mode
    check_func = _check_url_downloadable if strict else _check_url_accessible_quick

    # Try to upgrade HTTP to HTTPS for better compatibility
    if url.startswith("http://"):
        https_url = url.replace("http://", "https://", 1)

        # Prefer HTTPS version
        if await check_func(https_url, timeout):
            logger.debug(f"Upgraded HTTP to HTTPS: {url} -> {https_url}")
            return https_url

        # HTTPS not available
        if strict:
            # Reject HTTP-only in strict mode (OpenAI won't accept it)
            logger.debug(
                f"Image URL only available via HTTP (rejected in strict mode): {url}"
            )
            return None
        # In lenient mode, can fall back to HTTP if needed
        logger.debug(f"HTTPS upgrade failed, trying HTTP in lenient mode: {url}")
        if await check_func(url, timeout):
            return url
        return None

    # Already HTTPS or other protocol - validate directly
    if await check_func(url, timeout):
        return url

    logger.debug(f"Image URL validation failed for {url}")
    return None


# =============================================================================
# View Image Tool
# =============================================================================


def create_view_image_tool(sandbox: Any | None = None) -> BaseTool:
    """Factory function to create the view_image tool.

    Args:
        sandbox: Optional PTCSandbox instance for reading images from sandbox paths.
                 If not provided, sandbox_paths parameter will not be available.

    Returns:
        A LangChain tool for viewing images.
    """

    @tool
    def view_image(
        urls: list[str] | None = None,
        base64_images: list[str] | None = None,
        sandbox_paths: list[str] | None = None,
    ) -> str:
        """Load images for visual analysis.

        Args:
            urls: Image URLs (HTTPS, JPEG/PNG/GIF/WebP)
            base64_images: Base64-encoded images
            sandbox_paths: Sandbox file paths (e.g., results/chart.png)

        Returns:
            Confirmation message. Images available after tool completes.
        """
        # Count total images
        url_count = len(urls) if urls else 0
        base64_count = len(base64_images) if base64_images else 0
        sandbox_count = len(sandbox_paths) if sandbox_paths else 0
        total = url_count + base64_count + sandbox_count

        if total == 0:
            return "No images provided. Please specify URLs, base64 images, or sandbox paths."

        parts = []
        if url_count > 0:
            parts.append(f"{url_count} URL(s)")
        if base64_count > 0:
            parts.append(f"{base64_count} base64 image(s)")
        if sandbox_count > 0:
            parts.append(f"{sandbox_count} sandbox file(s)")

        return f"Loading {total} image(s) for viewing: {', '.join(parts)}..."

    return view_image


# =============================================================================
# View Image Middleware
# =============================================================================


class ViewImageMiddleware(AgentMiddleware):
    """Middleware that intercepts view_image tool calls and formats images.

    Formats images as HumanMessage content blocks in OpenAI-compatible format.
    This middleware solves the problem that many LLM APIs don't support
    images in tool messages (ToolMessage), but they do support images
    in user messages (HumanMessage).

    When the agent calls view_image, this middleware:
    1. Executes the tool to get the basic acknowledgment message
    2. Validates image URLs if enabled (checks accessibility)
    3. Formats all images into OpenAI-compatible content blocks
    4. Returns a Command that injects both:
       - The ToolMessage (for tool call completion)
       - A HumanMessage with the images (for vision model processing)

    Attributes:
        validate_urls: Whether to validate URL accessibility before sending
        strict_validation: If True, fully downloads and decodes images for validation
        sandbox: Optional PTCSandbox instance for reading images from sandbox paths
    """

    # Tool name to intercept
    TOOL_NAME = "view_image"

    # MIME type mapping for image extensions
    MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    def __init__(
        self,
        *,
        validate_urls: bool = True,
        strict_validation: bool = True,
        sandbox: Any | None = None,
    ) -> None:
        """Initialize the ViewImageMiddleware.

        Args:
            validate_urls: Whether to validate URL accessibility before sending.
                          When True, inaccessible URLs are silently skipped.
                          Default: True
            strict_validation: If True, uses full image download and decode validation
                              (matches OpenAI Vision API behavior). If False, uses
                              quick HEAD request check. Default: True
            sandbox: Optional PTCSandbox instance for reading images from sandbox paths.
                    If not provided, sandbox_paths in view_image will be ignored.
        """
        super().__init__()
        self.validate_urls = validate_urls
        self.strict_validation = strict_validation
        self.sandbox = sandbox

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        """Synchronous wrapper - delegates to async implementation.

        Note: Image validation requires async, so this sync wrapper is limited.
        For production use, prefer async execution via awrap_tool_call.
        """
        tool_call = request.tool_call
        tool_name = tool_call.get("name")

        # Pass through non-target tools
        if tool_name != self.TOOL_NAME:
            return handler(request)

        # For sync execution, just run the tool without image injection
        # (validation is async-only)
        logger.warning(
            "[VIEW_IMAGE] Sync execution detected. Images will not be injected. "
            "Use async execution for full functionality."
        )
        return handler(request)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Async wrapper that intercepts view_image and injects images as HumanMessage.

        Args:
            request: Tool call request containing tool_call dict with name, args, id
            handler: Next handler in middleware chain

        Returns:
            Command with updated messages (ToolMessage + HumanMessage with images),
            or the original ToolMessage if no valid images
        """
        tool_call = request.tool_call
        tool_name = tool_call.get("name")

        # Pass through non-target tools
        if tool_name != self.TOOL_NAME:
            return await handler(request)

        tool_call_id = tool_call.get("id", "unknown")
        tool_args = tool_call.get("args", {})

        logger.debug(f"[VIEW_IMAGE] Intercepting view_image call (id: {tool_call_id})")

        # Execute the tool to get the acknowledgment message
        result = await handler(request)

        # Extract image sources from tool arguments
        urls_raw = tool_args.get("urls")
        base64_images_raw = tool_args.get("base64_images")
        sandbox_paths_raw = tool_args.get("sandbox_paths")

        # Validate that list arguments are actually lists, not strings
        validation_errors = []
        for raw_value, param_name in [
            (urls_raw, "urls"),
            (base64_images_raw, "base64_images"),
            (sandbox_paths_raw, "sandbox_paths"),
        ]:
            error = _validate_list_arg(raw_value, param_name)
            if error:
                validation_errors.append(error)

        if validation_errors:
            return ToolMessage(
                content=f"Error: {' '.join(validation_errors)}",
                tool_call_id=tool_call_id,
            )

        urls = urls_raw or []
        base64_images = base64_images_raw or []
        sandbox_paths = sandbox_paths_raw or []

        # Build multimodal content blocks
        content_blocks = []
        failed_urls = []
        failed_sandbox_paths = []

        # Process sandbox paths first (download and convert to base64)
        if sandbox_paths and self.sandbox:
            for path in sandbox_paths:
                try:
                    # Download file bytes from sandbox
                    file_bytes = await asyncio.to_thread(
                        self.sandbox.download_file_bytes, path
                    )
                    if file_bytes:
                        # Determine MIME type from extension
                        ext = Path(path).suffix.lower()
                        mime_type = self.MIME_TYPES.get(ext, "image/png")

                        # Encode as base64 data URI
                        b64_string = base64.b64encode(file_bytes).decode("utf-8")
                        data_uri = f"data:{mime_type};base64,{b64_string}"

                        content_blocks.append(
                            {"type": "image_url", "image_url": {"url": data_uri}}
                        )
                        logger.debug(
                            f"[VIEW_IMAGE] Loaded sandbox image: {path} "
                            f"({len(file_bytes)} bytes, {mime_type})"
                        )
                    else:
                        failed_sandbox_paths.append(path)
                        logger.warning(f"[VIEW_IMAGE] Failed to download: {path}")
                except (OSError, ValueError) as e:
                    failed_sandbox_paths.append(path)
                    logger.warning(
                        f"[VIEW_IMAGE] Error loading sandbox image {path}: {e}"
                    )
        elif sandbox_paths and not self.sandbox:
            # Sandbox not available but paths were requested
            failed_sandbox_paths.extend(sandbox_paths)
            logger.warning(
                "[VIEW_IMAGE] sandbox_paths provided but no sandbox available"
            )

        # Process URLs (with optional validation)
        for url in urls:
            if self.validate_urls:
                try:
                    validated_url = await validate_image_url(
                        url, strict=self.strict_validation
                    )
                    if validated_url:
                        content_blocks.append(
                            {"type": "image_url", "image_url": {"url": validated_url}}
                        )
                        logger.debug(f"[VIEW_IMAGE] Validated URL: {validated_url}")
                    else:
                        failed_urls.append(url)
                        logger.warning(f"[VIEW_IMAGE] URL validation failed: {url}")
                except (httpx.RequestError, OSError, ValueError) as e:
                    failed_urls.append(url)
                    logger.warning(
                        f"[VIEW_IMAGE] URL validation error for {url}: {e}"
                    )
            else:
                content_blocks.append({"type": "image_url", "image_url": {"url": url}})

        # Process base64 images (add data URI prefix if missing)
        for img in base64_images:
            if not img.startswith("data:"):
                # Default to PNG format if no prefix
                img = f"data:image/png;base64,{img}"
            content_blocks.append({"type": "image_url", "image_url": {"url": img}})
            logger.debug(f"[VIEW_IMAGE] Added base64 image ({len(img)} chars)")

        # If no valid images, return original result with updated message
        if not content_blocks:
            error_parts = []
            if failed_urls:
                error_parts.append(f"{len(failed_urls)} URL(s) were inaccessible")
            if failed_sandbox_paths:
                error_parts.append(f"{len(failed_sandbox_paths)} sandbox path(s) could not be read")
            if error_parts:
                error_msg = f"Failed to load images. {' and '.join(error_parts)}."
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                )
            return result

        # Build the HumanMessage with images
        image_count = len(content_blocks)

        # Add descriptive text before images
        content_blocks.insert(
            0, {"type": "text", "text": f"[Viewing {image_count} image(s)]"}
        )

        # Add note about failed sources if any
        failed_notes = []
        if failed_urls:
            failed_notes.append(f"{len(failed_urls)} URL(s)")
        if failed_sandbox_paths:
            failed_notes.append(f"{len(failed_sandbox_paths)} sandbox path(s)")
        if failed_notes:
            content_blocks.append(
                {
                    "type": "text",
                    "text": f"[Note: {' and '.join(failed_notes)} could not be loaded and were skipped]",
                }
            )

        human_message = HumanMessage(content=content_blocks)  # type: ignore[arg-type]

        total_failed = len(failed_urls) + len(failed_sandbox_paths)
        logger.info(
            f"[VIEW_IMAGE] Injecting {image_count} image(s) as HumanMessage "
            f"(failed: {total_failed})"
        )

        # Return Command with both ToolMessage and HumanMessage
        return Command(
            update={
                "messages": [
                    result,  # ToolMessage for tool call completion
                    human_message,  # Images as HumanMessage for vision model
                ]
            }
        )


# =============================================================================
# Public API
# =============================================================================

__all__ = ["ViewImageMiddleware", "create_view_image_tool", "validate_image_url"]
