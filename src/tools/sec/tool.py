"""
LangChain tool for SEC filing extraction.

Provides a unified interface to fetch and parse SEC filings (10-K, 10-Q).
Uses edgartools for direct SEC EDGAR access with structured section extraction.
Falls back to crawl4ai + regex if edgartools fails.
"""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Tuple

from langchain_core.tools import StructuredTool

from src.tools.decorators import log_io
from .types import (
    FilingType,
    DEFAULT_10K_SECTIONS,
    DEFAULT_10Q_SECTIONS,
)
from .parsers.base import ParsingFailedError
from .earnings_call import (
    fetch_matching_earnings_call,
    format_earnings_call_section,
)
from .eight_k import (
    fetch_8k_filings,
    format_8k_filings,
    find_recent_8k_filings,
    format_8k_reminder,
    DEFAULT_8K_DAYS,
)

logger = logging.getLogger(__name__)

# Thread pool for running blocking edgartools calls
_executor = ThreadPoolExecutor(max_workers=3)


def _get_sec_filing_edgartools_blocking(
    symbol: str,
    filing_type: FilingType,
    sections: Optional[List[str]] = None,
    include_financials: bool = True,
    output_format: str = "markdown",
) -> Dict[str, Any]:
    """
    Get SEC filing using edgartools (blocking - runs in thread pool).

    Args:
        symbol: Stock ticker symbol
        filing_type: FilingType enum
        sections: Optional list of sections to extract
        include_financials: Include financial statements and metrics
        output_format: "markdown" (default) or "dict"

    Returns:
        Dict with filing data or raises ParsingFailedError
    """
    from .parsers.edgartools_parser import EdgarToolsParser

    parser = EdgarToolsParser()
    return parser.parse_filing(
        symbol=symbol,
        filing_type=filing_type,
        sections=sections,
        include_financials=include_financials,
        output_format=output_format,
    )


def _fetch_sec_filing_blocking(
    symbol: str,
    filing_type: FilingType,
    sections: Optional[List[str]],
    include_financials: bool,
    output_format: str,
) -> Tuple[Any, Optional[str]]:
    """
    Blocking helper to fetch SEC filing content (runs in thread pool).

    Returns:
        Tuple of (filing_content, filing_date_str) or (error_dict, None)
    """
    filing_date_str = None

    logger.debug(f"Fetching {filing_type.value} filing for {symbol} using edgartools")

    try:
        result = _get_sec_filing_edgartools_blocking(
            symbol=symbol,
            filing_type=filing_type,
            sections=sections,
            include_financials=include_financials,
            output_format=output_format,
        )

        # Extract filing date from markdown for earnings call matching
        if isinstance(result, str) and "**Filing Date:**" in result:
            match = re.search(r'\*\*Filing Date:\*\*\s*(\d{4}-\d{2}-\d{2})', result)
            if match:
                filing_date_str = match.group(1)

        return result, filing_date_str

    except ParsingFailedError as e:
        logger.warning(f"edgartools failed: {e}")
        return {
            "error": str(e),
            "symbol": symbol,
            "filing_type": filing_type.value,
        }, None

    except Exception as e:
        logger.warning(f"edgartools error: {e}")
        return {
            "error": f"Unexpected error: {e}",
            "symbol": symbol,
            "filing_type": filing_type.value,
        }, None


async def _fetch_sec_filing(
    symbol: str,
    filing_type: FilingType,
    sections: Optional[List[str]],
    include_financials: bool,
    output_format: str,
) -> Tuple[Any, Optional[str]]:
    """
    Async fetch SEC filing content using thread pool for blocking calls.

    Returns:
        Tuple of (filing_content, filing_date_str) or (error_dict, None)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _fetch_sec_filing_blocking,
        symbol,
        filing_type,
        sections,
        include_financials,
        output_format,
    )


async def get_sec_filing_async(
    symbol: str,
    filing_type: str = "10-K",
    sections: Optional[List[str]] = None,
    use_defaults: bool = True,
    include_financials: bool = True,
    include_earnings_call: bool = True,
    output_format: str = "markdown",
) -> Any:
    """
    Async implementation of SEC filing extraction with parallel fetching.

    Fetches SEC filing first (need filing_date), then fetches earnings call
    and nearby 8-K filings in parallel.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "MSFT")
        filing_type: "10-K" (annual), "10-Q" (quarterly), or "8-K" (event-driven)
        sections: List of sections to extract. If None, uses defaults or all.
        use_defaults: If True and sections is None, extract only essential sections.
        include_financials: If True, include financial statements and metrics.
        include_earnings_call: If True, include matching earnings call transcript.
        output_format: "markdown" (default) or "dict"

    Returns:
        Formatted markdown string or dict with filing data.
    """
    # Validate filing type
    try:
        ftype = FilingType(filing_type)
    except ValueError:
        return {
            "error": f"Invalid filing type: {filing_type}. Use '10-K', '10-Q', or '8-K'."
        }

    # Handle 8-K separately - fetch all filings from last 90 days
    if ftype == FilingType.FORM_8K:
        return await _fetch_8k_filings(symbol)

    # Determine sections to extract for 10-K/10-Q
    if sections is None and use_defaults:
        if ftype == FilingType.FORM_10K:
            sections = DEFAULT_10K_SECTIONS
        else:
            sections = DEFAULT_10Q_SECTIONS

    # Step 1: Fetch SEC filing (sequential - need filing_date first)
    result, filing_date_str = await _fetch_sec_filing(
        symbol=symbol,
        filing_type=ftype,
        sections=sections,
        include_financials=include_financials,
        output_format=output_format,
    )

    # Check for errors
    if isinstance(result, dict) and "error" in result:
        return result

    # If no filing date or not markdown, return as-is
    if not filing_date_str or not isinstance(result, str):
        return result

    # Parse filing date for parallel fetches
    try:
        filing_date_obj = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.warning(f"Failed to parse filing date: {filing_date_str}")
        return result

    # Step 2: Fetch earnings call and nearby 8-Ks IN PARALLEL
    tasks = []

    if include_earnings_call:
        tasks.append(
            asyncio.create_task(
                fetch_matching_earnings_call(symbol, filing_date_obj),
                name="earnings_call"
            )
        )

    # Always fetch recent 8-K filings (last 90 days) for 10-K/10-Q
    tasks.append(
        asyncio.create_task(
            find_recent_8k_filings(symbol, max_days=DEFAULT_8K_DAYS),
            name="recent_8k"
        )
    )

    if not tasks:
        return result

    # Wait for all parallel tasks
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 3: Assemble final output
    output = result

    for i, task in enumerate(tasks):
        task_result = results[i]

        if isinstance(task_result, Exception):
            logger.warning(f"Task {task.get_name()} failed: {task_result}")
            continue

        if task.get_name() == "earnings_call" and task_result:
            try:
                transcript, fiscal_year, quarter, call_date = task_result
                earnings_section = format_earnings_call_section(
                    transcript, fiscal_year, quarter, call_date, filing_date_obj
                )
                output += earnings_section
            except Exception as e:
                logger.warning(f"Failed to format earnings call: {e}")

        elif task.get_name() == "recent_8k" and task_result:
            try:
                reminder_section = format_8k_reminder(
                    task_result, filing_type, max_days=DEFAULT_8K_DAYS
                )
                output += reminder_section
            except Exception as e:
                logger.warning(f"Failed to format 8-K reminder: {e}")

    return output


async def _fetch_8k_filings(symbol: str) -> str:
    """
    Fetch all 8-K filings from the last 90 days for a symbol.

    Returns formatted markdown with all 8-K filings, each with items and press release.
    """
    filings = await fetch_8k_filings(symbol, max_days=DEFAULT_8K_DAYS)
    return format_8k_filings(symbol, filings, max_days=DEFAULT_8K_DAYS)


async def _get_sec_filing_tool_impl(
    symbol: Annotated[str, "Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'NVDA')"],
    filing_type: Annotated[str, "Type of SEC filing: '10-K' (annual), '10-Q' (quarterly), or '8-K' (event-driven)"] = "10-K",
    include_financials: Annotated[bool, "Include financial statements and key metrics (10-K/10-Q only)"] = True,
    include_earnings_call: Annotated[bool, "Include matching earnings call transcript (10-K/10-Q only)"] = True,
) -> str:
    """
    Fetch SEC filing (10-K, 10-Q, or 8-K) with related information.

    Retrieves the most recent SEC filing with essential sections, financial
    statements, earnings call transcript, and reminders about nearby 8-K
    filings. Returns formatted markdown combining all sources.
    """
    return await get_sec_filing_async(
        symbol=symbol,
        filing_type=filing_type,
        sections=None,  # Use default essential sections
        use_defaults=True,  # Always extract essential sections only
        include_financials=include_financials,
        include_earnings_call=include_earnings_call,
        output_format="markdown",  # Always return markdown
    )


# Apply decorator and create tool using StructuredTool for async support
_decorated_impl = log_io(_get_sec_filing_tool_impl)

get_sec_filing = StructuredTool.from_function(
    coroutine=_decorated_impl,
    name="get_sec_filing",
    description="""Fetch SEC filing (10-K, 10-Q, or 8-K) with related information.

Retrieves SEC filings with essential sections, financial statements,
earnings call transcript, and recent 8-K filings. Returns formatted
markdown combining all sources.

IMPORTANT - Citation Requirement:
The returned content includes source URLs linking to official SEC EDGAR
filings. When using information from this filing in your response, you MUST
cite the source URLs to ensure proper attribution and allow users to verify
the information directly from SEC.gov.

IMPORTANT - Choosing filing_type:
- Use "10-K" (annual) for comprehensive analysis when recent quarterly
  data is not critical. 10-K provides full-year financials with detailed
  business description, complete risk factors, and audited statements.
- Use "10-Q" (quarterly) when you need the MOST RECENT financial data.
  10-Q is filed ~45 days after quarter end, so it's more current than
  10-K which is filed ~60 days after fiscal year end.
- Use "8-K" (event-driven) to get ALL 8-K filings from the last 90 days,
  including earnings announcements, forward guidance, and material events.

Rule of thumb: Choose strategically based on the goal and current date.

Args:
    symbol: Stock ticker symbol (e.g., "AAPL", "MSFT", "NVDA")
    filing_type: Type of SEC filing:
        - "10-K": Annual report (comprehensive, audited, full year)
        - "10-Q": Quarterly report (more recent, unaudited, interim)
        - "8-K": All event-driven reports from last 90 days
    include_financials: If True (default), include financial statements
        (balance sheet, income statement, cash flow) and key metrics.
    include_earnings_call: If True (default), include the earnings call
        transcript from the same fiscal period. Automatically matches
        the call date to the SEC filing date.

Returns:
    For 10-K/10-Q:
    - Filing metadata (date, period, source URL)
    - Key financial metrics summary
    - Financial statements as structured tables
    - Essential sections (MD&A, Risk Factors, etc.)
    - Earnings call transcript (when available and requested)
    - List of recent 8-K filings (last 90 days)

    For 8-K:
    - All 8-K filings from the last 90 days
    - Each filing includes: date, items, source URL, press release (if any)""",
)
