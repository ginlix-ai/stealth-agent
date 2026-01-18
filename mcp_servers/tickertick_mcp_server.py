#!/usr/bin/env python3
"""
Tickertick MCP Server - Self-contained MCP server for financial news
Provides tools to fetch ticker news, curated news, and entity news from Tickertick API

Usage:
    python tickertick_mcp_server.py

For LangGraph integration, configure this as an MCP server with stdio transport.
"""

from mcp.server.fastmcp import FastMCP
from typing import List
import requests
from datetime import datetime, timezone

# Create the MCP server
mcp = FastMCP("TickertickMCP")

# API Configuration
FEED_URL = 'https://api.tickertick.com/feed'
TICKERS_URL = 'https://api.tickertick.com/tickers'
RATE_LIMIT = 10  # 10 requests per minute limit


def _get_feed(query: str, limit: int = 30, last_id: str = None) -> dict:
    """Get feed data from Tickertick API"""
    url = f"{FEED_URL}?q={query}"

    if limit:
        url += f"&n={limit}"

    if last_id:
        url += f"&last={last_id}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return _convert_timestamp_ms_to_iso(data)
        else:
            return {"error": f"API request failed with status code {response.status_code}"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def _convert_timestamp_ms_to_iso(response: dict) -> dict:
    """Convert timestamp in milliseconds to ISO format"""
    if 'stories' not in response:
        return response

    for story in response['stories']:
        if 'time' in story:
            timestamp_sec = story['time'] / 1000
            story['time'] = datetime.fromtimestamp(timestamp_sec, timezone.utc).isoformat()
    return response


# MCP Tools

@mcp.tool()
def get_ticker_news(ticker: str, limit: int = 10) -> dict:
    """
    Get news for a specific ticker symbol.

    Args:
        ticker: The ticker symbol (e.g., AAPL, MSFT, TSLA)
        limit: Maximum number of news items to return (default: 10, max: 50)

    Returns:
        A dictionary containing news items related to the ticker
    """
    query = f"z:{ticker}"
    return _get_feed(query, limit)


@mcp.tool()
def get_broad_ticker_news(ticker: str, limit: int = 10) -> dict:
    """
    Get broader news for a specific ticker symbol.
    This includes mentions and related news beyond direct ticker matches.

    Args:
        ticker: The ticker symbol (e.g., AAPL, MSFT, TSLA)
        limit: Maximum number of news items to return (default: 10, max: 50)

    Returns:
        A dictionary containing broader news items related to the ticker
    """
    query = f"tt:{ticker}"
    return _get_feed(query, limit)


@mcp.tool()
def get_news_from_source(source: str, limit: int = 10) -> dict:
    """
    Get news from a specific source.

    Args:
        source: The news source (e.g., bloomberg, wsj, cnbc, reuters)
        limit: Maximum number of news items to return (default: 10, max: 50)

    Returns:
        A dictionary containing news items from the specified source
    """
    query = f"s:{source}"
    return _get_feed(query, limit)


@mcp.tool()
def get_news_for_multiple_tickers(tickers: List[str], limit: int = 10) -> dict:
    """
    Get news for multiple ticker symbols.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "TSLA"])
        limit: Maximum number of news items to return (default: 10, max: 50)

    Returns:
        A dictionary containing news items related to any of the specified tickers
    """
    ticker_terms = [f"tt:{ticker}" for ticker in tickers]
    query = f"(or {' '.join(ticker_terms)})"
    return _get_feed(query, limit)


@mcp.tool()
def get_curated_news(limit: int = 10) -> dict:
    """
    Get curated news from top financial/technology sources.
    This is helpful to get a broad overview of the market.

    Args:
        limit: Maximum number of news items to return (default: 10, max: 50)

    Returns:
        A dictionary containing curated news items
    """
    query = "T:curated"
    return _get_feed(query, limit)


@mcp.tool()
def get_entity_news(entity: str, limit: int = 10) -> dict:
    """
    Get news about a specific entity (person, company, etc.)

    Args:
        entity: The entity name (e.g., "Elon Musk", "Trump", "Warren Buffett")
        limit: Maximum number of news items to return (default: 10, max: 50)

    Returns:
        A dictionary containing news items related to the entity
    """
    # Replace spaces with underscores as required by the API
    entity_formatted = entity.lower().replace(" ", "_")
    query = f"E:{entity_formatted}"
    return _get_feed(query, limit)


@mcp.tool()
def search_tickers(query: str, limit: int = 5) -> dict:
    """
    Search for tickers matching the query.

    Args:
        query: The search query (e.g., "Apple", "TSLA", "Microsoft")
        limit: Maximum number of results to return (default: 5, max: 20)

    Returns:
        A dictionary containing matching ticker symbols and company names
    """
    url = f"{TICKERS_URL}?p={query}&n={limit}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API request failed with status code {response.status_code}"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


# Run the server
if __name__ == "__main__":
    mcp.run(transport="stdio")
