"""
Crawler implementation using Crawl4AI.

This module provides a fully async Crawler class that uses Crawl4AI for web content
extraction.
"""

import logging
from typing import Optional

from .crawl4ai_client import Crawl4AIClient

logger = logging.getLogger(__name__)


class Crawl4AICrawler:
    """
    Async crawler implementation using Crawl4AI for content extraction.

    Features:
    - Fully async API for true concurrency
    - No API keys required
    - No rate limits
    - Self-hosted and fully controllable
    - Optimized for LLM consumption

    Note: For fault tolerance and circuit breaker, use SafeCrawlerWrapper instead.
    """

    def __init__(
        self,
        headless: bool = True,
        verbose: bool = False,
        cache_mode: Optional[str] = None,
        wait_until: str = "domcontentloaded",
        page_timeout: int = 60000,
        delay_before_return: int = 3,
        wait_for_selector: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize Crawl4AI crawler.

        Args:
            headless: Run browser in headless mode (default: True)
            verbose: Enable verbose logging (default: False)
            cache_mode: Caching strategy - None for default, 'bypass' to force fresh
            wait_until: When to consider page loaded (default: "domcontentloaded")
            page_timeout: Maximum time to wait for page load in ms (default: 60000)
            delay_before_return: Seconds to wait after load for JS rendering (default: 3)
            wait_for_selector: Optional CSS selector to wait for before extraction
            user_agent: Custom user agent string
        """
        self.headless = headless
        self.verbose = verbose
        self.cache_mode = cache_mode
        self.wait_until = wait_until
        self.page_timeout = page_timeout
        self.delay_before_return = delay_before_return
        self.wait_for_selector = wait_for_selector
        self.user_agent = user_agent
        logger.debug(
            f"Initialized Crawl4AICrawler "
            f"(headless={headless}, wait_until={wait_until}, "
            f"delay={self.delay_before_return}s, cache_mode={cache_mode})"
        )

    def _create_client(self) -> Crawl4AIClient:
        """Create a configured Crawl4AI client."""
        return Crawl4AIClient(
            headless=self.headless,
            verbose=self.verbose,
            wait_until=self.wait_until,
            page_timeout=self.page_timeout,
            delay_before_return=self.delay_before_return,
            wait_for_selector=self.wait_for_selector,
            user_agent=self.user_agent,
        )

    async def crawl(self, url: str) -> str:
        """
        Crawl a URL and return markdown content.

        Args:
            url: The URL to crawl

        Returns:
            Markdown content from the page

        Raises:
            Exception: If crawling fails
        """
        client = self._create_client()
        title, html_content, markdown_content = await client.crawl(
            url, cache_mode=self.cache_mode
        )
        return markdown_content

    async def crawl_with_metadata(self, url: str) -> tuple[str, str, str]:
        """
        Crawl a URL and return full metadata.

        Args:
            url: The URL to crawl

        Returns:
            Tuple of (title, html_content, markdown_content)

        Raises:
            Exception: If crawling fails
        """
        client = self._create_client()
        return await client.crawl(url, cache_mode=self.cache_mode)
