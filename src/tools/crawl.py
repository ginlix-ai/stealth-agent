"""
Web crawling tool using Crawl4AI.

Provides async web crawling that returns raw markdown content.
For LLM-based extraction, use web_fetch_tool instead.
"""

import logging
from typing import Annotated

from langchain_core.tools import StructuredTool

from .decorators import log_io
from .crawler.crawl4ai_crawler import Crawl4AICrawler

logger = logging.getLogger(__name__)


async def _crawl_impl(
    url: Annotated[str, "The url to crawl."],
) -> str:
    """
    Use this to crawl a url and get readable content in markdown format using Crawl4AI.

    This tool uses the open-source Crawl4AI library for self-hosted web crawling,
    providing LLM-optimized content extraction without API keys or rate limits.

    The tool is configured with sensible defaults for JavaScript-heavy sites:
    - Waits for DOM to be ready (domcontentloaded event)
    - Gives JS frameworks 3 seconds to render after DOM ready
    - Uses realistic browser configuration to avoid bot detection
    - 60 second timeout for slow-loading sites

    Returns full content without truncation for comprehensive analysis.
    """
    try:
        crawler = Crawl4AICrawler(
            headless=True,
            verbose=False,
            wait_until="domcontentloaded",
            page_timeout=60000,
            delay_before_return=3,
        )
        markdown = await crawler.crawl(url)

        return {"url": url, "crawled_content": markdown}
    except BaseException as e:
        error_msg = f"Failed to crawl. Error: {repr(e)}"
        logger.error(error_msg)
        return error_msg


# Apply decorator and create async tool
_decorated_impl = log_io(_crawl_impl)

crawl_tool = StructuredTool.from_function(
    coroutine=_decorated_impl,
    name="crawl",
    description="""Use this to crawl a url and get readable content in markdown format using Crawl4AI.

This tool uses the open-source Crawl4AI library for self-hosted web crawling,
providing LLM-optimized content extraction without API keys or rate limits.

The tool is configured with sensible defaults for JavaScript-heavy sites:
- Waits for DOM to be ready (domcontentloaded event)
- Gives JS frameworks 3 seconds to render after DOM ready
- Uses realistic browser configuration to avoid bot detection
- 60 second timeout for slow-loading sites

Returns full content without truncation for comprehensive analysis.""",
)
