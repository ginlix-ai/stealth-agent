"""
Sitemap fetching using Crawl4AI's AsyncUrlSeeder.

This module provides sitemap discovery and summarization for web_fetch,
enabling the extraction LLM to suggest alternative URLs when content
is not found on the current page.
"""

import logging
import warnings
from typing import Optional
from urllib.parse import urlparse
from collections import defaultdict

logger = logging.getLogger(__name__)

# Suppress "Task was destroyed but it is pending" warnings from asyncio
# This is a known issue with Crawl4AI's AsyncUrlSeeder internal task management
# when operations are cancelled/timed out. The warning is harmless but noisy.
warnings.filterwarnings(
    "ignore",
    message=".*Task was destroyed but it is pending.*",
    category=RuntimeWarning,
)
# Also suppress via asyncio logger (some versions log as ERROR instead of warning)
logging.getLogger("asyncio").setLevel(logging.WARNING)


def _get_sitemap_config() -> dict:
    """Get sitemap config from conf.yaml."""
    try:
        from src.config.loader import load_yaml_config
        config = load_yaml_config("conf.yaml")
        return config.get("web_fetch", {})
    except Exception:
        return {}


async def fetch_sitemap_urls(domain: str, max_urls: int = 100, timeout: float = 10.0) -> list[dict]:
    """
    Fetch sitemap URLs using Crawl4AI's AsyncUrlSeeder.

    Args:
        domain: Domain to fetch sitemap from (e.g., "example.com")
        max_urls: Maximum number of URLs to return
        timeout: Timeout in seconds for sitemap fetch (default: 10s)

    Returns:
        List of dicts with "url" and optional "title" keys.
        Returns empty list if sitemap unavailable or times out.
    """
    import asyncio

    try:
        from crawl4ai import AsyncUrlSeeder, SeedingConfig

        async def _fetch():
            async with AsyncUrlSeeder() as seeder:
                config = SeedingConfig(
                    source="sitemap",
                    extract_head=False,  # Skip head extraction (faster, avoids extra requests)
                    max_urls=max_urls,
                    live_check=False,    # Skip verification for speed
                )
                return await seeder.urls(domain, config)

        # Run with timeout to avoid hanging on large sitemaps
        # Use create_task + wait to allow graceful cleanup on timeout
        task = asyncio.create_task(_fetch())
        try:
            urls = await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            logger.debug(f"Fetched {len(urls)} URLs from sitemap for {domain}")
            return urls
        except asyncio.TimeoutError:
            logger.debug(f"Sitemap fetch timed out for {domain} (>{timeout}s)")
            # Cancel the task and give it a moment to clean up internal tasks
            task.cancel()
            try:
                # Allow cancellation to propagate through internal tasks
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            return []

    except ImportError:
        logger.warning("AsyncUrlSeeder not available in crawl4ai")
        return []
    except Exception as e:
        logger.debug(f"Sitemap fetch failed for {domain}: {e}")
        return []


def summarize_sitemap(urls: list[dict], max_examples: int = 3) -> str:
    """
    Create high-level summary of sitemap URLs grouped by path prefix.

    Groups URLs by their first path segment and shows representative
    examples with titles if available.

    Args:
        urls: List of dicts with "url" key and optional "title"/"head_data"
        max_examples: Maximum example URLs per path prefix

    Returns:
        Formatted string summary of site structure
    """
    if not urls:
        return ""

    # Group by first path segment
    groups = defaultdict(list)
    for item in urls:
        url = item.get("url", "")
        if not url:
            continue
        path = urlparse(url).path
        # Extract first path segment as prefix
        segments = path.strip("/").split("/")
        prefix = "/" + segments[0] if segments and segments[0] else "/"
        groups[prefix].append(item)

    if not groups:
        return ""

    # Format summary, sorted by count descending
    lines = []
    for prefix, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        examples = items[:max_examples]
        example_strs = []
        for e in examples:
            url_str = e.get("url", "")
            # Try to get title from head_data or direct title field
            title = ""
            if e.get("head_data") and e["head_data"].get("title"):
                title = e["head_data"]["title"][:40]
            elif e.get("title"):
                title = e["title"][:40]

            if title:
                example_strs.append(f"{url_str} ({title})")
            else:
                example_strs.append(url_str)

        lines.append(f"- {prefix} ({len(items)} pages): {', '.join(example_strs)}")

    return "\n".join(lines)


async def get_sitemap_summary(
    url: str,
    max_urls: Optional[int] = None,
    max_examples: Optional[int] = None,
) -> str:
    """
    Get sitemap summary for a URL's domain.

    Fetches sitemap and creates a high-level summary suitable for
    injection into LLM context.

    Args:
        url: Any URL from the target domain
        max_urls: Maximum URLs to fetch (default from config or 100)
        max_examples: Max examples per prefix (default from config or 3)

    Returns:
        Formatted sitemap summary, or empty string if unavailable
    """
    # Get config defaults
    config = _get_sitemap_config()
    if not config.get("sitemap_enabled", True):
        return ""

    # Skip sitemap fetch if crawler circuit breaker is open
    # This reduces load when the crawler is having issues
    try:
        from .safe_wrapper import get_safe_crawler_sync
        safe_crawler = get_safe_crawler_sync()
        if not safe_crawler.is_healthy():
            logger.debug("Skipping sitemap fetch - crawler circuit is open")
            return ""
    except Exception:
        pass  # Continue if safe_wrapper not available

    if max_urls is None:
        max_urls = config.get("sitemap_max_urls", 100)
    if max_examples is None:
        max_examples = config.get("sitemap_max_examples", 3)

    try:
        domain = urlparse(url).netloc
        if not domain:
            return ""

        # Fetch sitemap URLs
        urls = await fetch_sitemap_urls(domain, max_urls)
        if not urls:
            return ""

        # Generate summary
        summary = summarize_sitemap(urls, max_examples)
        if summary:
            logger.debug(f"Generated sitemap summary for {domain} ({len(urls)} URLs)")
        return summary

    except Exception as e:
        logger.debug(f"Sitemap summary failed for {url}: {e}")
        return ""
