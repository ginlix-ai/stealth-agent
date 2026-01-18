"""
Crawl4AI client for web crawling and content extraction.

This module provides an async wrapper around Crawl4AI's AsyncWebCrawler
for extracting clean, LLM-ready content from web pages.

Uses a managed browser singleton to prevent race conditions in concurrent
crawl operations.
"""

import asyncio
import atexit
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crawl4ai import AsyncWebCrawler

logger = logging.getLogger(__name__)


class Crawl4AIBrowserManager:
    """
    Manages a shared browser instance for all crawl operations.

    This singleton handles browser lifecycle (lazy init, graceful shutdown).
    Concurrency control is handled by SafeCrawlerWrapper's circuit breaker.

    Note: This class focuses only on browser lifecycle management.
    Concurrency limits and fault tolerance are handled by SafeCrawlerWrapper.
    """

    _instance: Optional["Crawl4AIBrowserManager"] = None
    _init_lock: asyncio.Lock = None

    def __init__(self):
        self._browser: Optional["AsyncWebCrawler"] = None
        self._browser_lock: asyncio.Lock = asyncio.Lock()
        self._browser_config = None
        logger.debug("Crawl4AI browser manager initialized")

    @classmethod
    async def get_instance(cls) -> "Crawl4AIBrowserManager":
        """Get or create the singleton browser manager."""
        if cls._init_lock is None:
            cls._init_lock = asyncio.Lock()

        async with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
                logger.debug("Created Crawl4AIBrowserManager singleton")
            return cls._instance

    async def _ensure_browser(self, browser_config) -> "AsyncWebCrawler":
        """Ensure browser is initialized, creating if needed."""
        from crawl4ai import AsyncWebCrawler

        async with self._browser_lock:
            if self._browser is None:
                logger.debug("Initializing shared browser instance")
                self._browser_config = browser_config
                self._browser = AsyncWebCrawler(config=browser_config)
                await self._browser.__aenter__()
                logger.info("Shared browser instance initialized")
            return self._browser

    async def crawl(self, url: str, browser_config, run_config) -> tuple[str, str, str]:
        """
        Execute crawl with managed browser.

        Note: Concurrency control is handled by SafeCrawlerWrapper.
        This method focuses only on executing the crawl.
        """
        browser = await self._ensure_browser(browser_config)

        try:
            result = await browser.arun(url=url, config=run_config)

            if not result.success:
                error_msg = f"Crawl4AI failed to crawl {url}: {result.error_message}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # Extract title
            title = result.metadata.get("title", "") if result.metadata else ""

            # Get cleaned HTML
            html_content = result.cleaned_html or result.html or ""

            # Get optimized markdown
            markdown_content = ""
            if result.markdown:
                markdown_content = (
                    result.markdown.fit_markdown
                    or result.markdown.raw_markdown
                    or ""
                )

            return title, html_content, markdown_content

        except Exception as e:
            error_str = str(e)
            # If browser was closed unexpectedly, reset it for next request
            if "has been closed" in error_str or "Target page" in error_str:
                logger.warning(f"Browser closed unexpectedly, will reset")
                await self._reset_browser()
            raise

    async def _reset_browser(self):
        """Reset browser instance after unexpected closure."""
        async with self._browser_lock:
            if self._browser is not None:
                try:
                    await self._browser.__aexit__(None, None, None)
                except Exception:
                    pass  # Browser already closed
                self._browser = None
                logger.info("Browser instance reset")

    async def shutdown(self):
        """Gracefully close the browser."""
        async with self._browser_lock:
            if self._browser is not None:
                try:
                    await self._browser.__aexit__(None, None, None)
                    logger.info("Shared browser instance shut down")
                except Exception as e:
                    logger.warning(f"Error during browser shutdown: {e}")
                finally:
                    self._browser = None

    @classmethod
    async def shutdown_instance(cls):
        """Shutdown the singleton instance if it exists."""
        if cls._instance is not None:
            await cls._instance.shutdown()
            cls._instance = None


def _shutdown_browser_sync():
    """Synchronous shutdown hook for atexit."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule shutdown in running loop
            loop.create_task(Crawl4AIBrowserManager.shutdown_instance())
        else:
            loop.run_until_complete(Crawl4AIBrowserManager.shutdown_instance())
    except Exception as e:
        logger.debug(f"Browser shutdown during exit: {e}")


# Register shutdown hook
atexit.register(_shutdown_browser_sync)


class Crawl4AIClient:
    """
    Async client for web crawling using Crawl4AI.

    Crawl4AI is an open-source, self-hosted crawler that produces
    LLM-optimized markdown output without API keys or rate limits.
    """

    def __init__(
        self,
        headless: bool = True,
        verbose: bool = False,
        wait_until: str = "domcontentloaded",
        page_timeout: int = 60000,
        delay_before_return: int = 3,
        wait_for_selector: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize Crawl4AI client.

        Args:
            headless: Run browser in headless mode (default: True)
            verbose: Enable verbose logging (default: False)
            wait_until: When to consider page loaded - "commit", "domcontentloaded",
                       "load", or "networkidle" (default: "domcontentloaded" + delay
                       for good balance between speed and JS rendering)
            page_timeout: Maximum time to wait for page load in milliseconds (default: 60000)
            delay_before_return: Seconds to wait after page load before extracting HTML,
                                allows JS frameworks time to render (default: 3)
            wait_for_selector: Optional CSS selector to wait for before extraction
            user_agent: Custom user agent string (default: Chrome-like agent)
        """
        self.headless = headless
        self.verbose = verbose
        self.wait_until = wait_until
        self.page_timeout = page_timeout
        self.delay_before_return = delay_before_return
        self.wait_for_selector = wait_for_selector
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if Crawl4AI is installed."""
        try:
            import crawl4ai
        except ImportError:
            logger.error(
                "Crawl4AI is not installed. Install with: "
                "pip install crawl4ai && crawl4ai-setup"
            )
            raise

    async def crawl(
        self,
        url: str,
        return_format: str = "html",
        cache_mode: Optional[str] = None,
        wait_until: Optional[str] = None,
        wait_for_selector: Optional[str] = None,
        delay: Optional[int] = None,
    ) -> tuple[str, str, str]:
        """
        Crawl a URL and extract content.

        Uses a shared browser instance to prevent race conditions in concurrent
        crawl operations.

        Args:
            url: The URL to crawl
            return_format: Format to return - 'html', 'markdown', or 'both' (default: 'html')
            cache_mode: Caching strategy - None for default, 'bypass' to force fresh fetch
            wait_until: Override default wait_until strategy for this request
            wait_for_selector: Override default wait_for_selector for this request
            delay: Override default delay_before_return for this request

        Returns:
            Tuple of (title, html_content, markdown_content)

        Raises:
            Exception: If crawling fails or Crawl4AI is not installed
        """
        from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode

        # Configure browser with better defaults for real browser mimicry
        browser_config = BrowserConfig(
            headless=self.headless,
            verbose=self.verbose,
            viewport_width=1920,
            viewport_height=1080,
            user_agent=self.user_agent,
        )

        # Configure crawler run with wait strategies
        run_config_kwargs = {
            "wait_until": wait_until or self.wait_until,
            "page_timeout": self.page_timeout,
            "delay_before_return_html": delay or self.delay_before_return,
        }

        # Add optional wait_for selector if specified
        selector = wait_for_selector or self.wait_for_selector
        if selector:
            run_config_kwargs["wait_for"] = selector

        # Set cache mode
        if cache_mode == "bypass":
            run_config_kwargs["cache_mode"] = CacheMode.BYPASS
        else:
            run_config_kwargs["cache_mode"] = CacheMode.ENABLED

        run_config = CrawlerRunConfig(**run_config_kwargs)

        # Use managed browser - fault tolerance handled by SafeCrawlerWrapper
        manager = await Crawl4AIBrowserManager.get_instance()
        return await manager.crawl(url, browser_config, run_config)
