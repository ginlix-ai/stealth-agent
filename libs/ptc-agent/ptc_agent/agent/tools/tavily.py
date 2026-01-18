"""Tavily search tool for web research.

Uses Tavily for URL discovery and fetches full webpage content.
"""

from typing import Annotated, Literal

import httpx
import structlog
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient

logger = structlog.get_logger(__name__)

# Lazy-initialized client to avoid import-time errors when API key is missing
_tavily_client: TavilyClient | None = None


def _get_tavily_client() -> TavilyClient:
    """Get or create the Tavily client (lazy initialization)."""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient()
    return _tavily_client


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return markdownify(response.text)
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        return f"Error fetching content from {url}: {e!s}"


@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 1)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Formatted search results with full webpage content
    """
    # Use Tavily to discover URLs
    try:
        search_results = _get_tavily_client().search(
            query,
            max_results=max_results,
            topic=topic,
        )
    except Exception as e:
        logger.exception("Tavily search failed", query=query)
        return f"ERROR: Search failed - {e}"

    # Fetch full content for each URL
    result_texts = []
    for result in search_results.get("results", []):
        url = result.get("url", "")
        title = result.get("title", "Untitled")

        if not url:
            continue  # Skip results without URL

        # Fetch webpage content
        content = fetch_webpage_content(url)

        result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
        result_texts.append(result_text)

    # Format final response
    return f"""Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""

