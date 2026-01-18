"""
Async 8-K filing utilities for SEC filings.

Provides functions to:
- Fetch all 8-K filings within a time range
- Format 8-K filings with full press release content
- Generate reminders about nearby 8-K filings for 10-K/10-Q
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Thread pool for running blocking edgartools calls
_executor = ThreadPoolExecutor(max_workers=3)

# SEC EDGAR identity (required by SEC)
SEC_IDENTITY = "OpenSource user@example.com"

# Default time range for 8-K listings (90 days = ~3 months)
DEFAULT_8K_DAYS = 90


def _init_edgar():
    """Initialize edgartools with SEC identity and SSL settings."""
    if os.getenv("EDGAR_VERIFY_SSL", "true").lower() == "false":
        os.environ["EDGAR_VERIFY_SSL"] = "false"

    from edgar import set_identity
    set_identity(SEC_IDENTITY)


def _get_press_release_markdown(obj: Any) -> Optional[str]:
    """
    Extract press release content as markdown from 8-K object.

    Args:
        obj: edgartools 8-K object

    Returns:
        Markdown content or None if no press release
    """
    if not getattr(obj, "has_press_release", False):
        return None

    try:
        press_releases = obj.press_releases
        if not press_releases:
            return None

        pr = press_releases[0]
        # Use to_markdown().md for proper table formatting
        if hasattr(pr, "to_markdown"):
            md_obj = pr.to_markdown()
            return md_obj.md if hasattr(md_obj, "md") else str(md_obj)
        elif hasattr(pr, "text"):
            return pr.text() if callable(pr.text) else str(pr.text)
    except Exception as e:
        logger.debug(f"Failed to extract press release: {e}")

    return None


def _fetch_8k_filings_blocking(
    symbol: str,
    max_days: int = DEFAULT_8K_DAYS,
    reference_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Blocking implementation to fetch all 8-K filings within a time range.

    Args:
        symbol: Stock ticker symbol
        max_days: Maximum days to look back from reference_date
        reference_date: Reference date (default: today)

    Returns:
        List of dicts with: filing_date, items, source_url, cik, has_press_release, press_release
    """
    try:
        _init_edgar()
        from edgar import Company
        from .types import FORM_8K_ITEMS

        company = Company(symbol)
        filings_8k = company.get_filings(form="8-K")

        if not filings_8k or len(filings_8k) == 0:
            return []

        ref_date = reference_date or date.today()
        cutoff_date = ref_date - timedelta(days=max_days)

        filings = []
        for i in range(min(50, len(filings_8k))):
            try:
                filing = filings_8k.get_filing_at(i)

                # Stop if we've gone past the cutoff date
                if filing.filing_date < cutoff_date:
                    break

                obj = filing.obj()
                filing_items = obj.items if hasattr(obj, "items") else []

                # Get item descriptions
                items_with_desc = []
                for item in filing_items:
                    desc = FORM_8K_ITEMS.get(item, "")
                    items_with_desc.append({"item": item, "description": desc})

                # Get press release content
                press_release = _get_press_release_markdown(obj)

                filings.append({
                    "filing_date": filing.filing_date,
                    "items": filing_items,
                    "items_with_desc": items_with_desc,
                    "source_url": filing.filing_url,
                    "cik": str(filing.cik),
                    "has_press_release": press_release is not None,
                    "press_release": press_release,
                })

            except Exception as e:
                logger.debug(f"Error processing 8-K at index {i}: {e}")
                continue

        # Sort by filing date (most recent first)
        filings.sort(key=lambda x: x["filing_date"], reverse=True)
        return filings

    except Exception as e:
        logger.warning(f"Failed to fetch 8-K filings for {symbol}: {e}")
        return []


async def fetch_8k_filings(
    symbol: str,
    max_days: int = DEFAULT_8K_DAYS,
    reference_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Async fetch all 8-K filings within a time range.

    Args:
        symbol: Stock ticker symbol
        max_days: Maximum days to look back (default: 90)
        reference_date: Reference date (default: today)

    Returns:
        List of 8-K filing info dicts, sorted most recent first
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _fetch_8k_filings_blocking,
        symbol,
        max_days,
        reference_date,
    )


def format_8k_filings(
    symbol: str,
    filings: List[Dict[str, Any]],
    max_days: int = DEFAULT_8K_DAYS,
) -> str:
    """
    Format all 8-K filings as markdown.

    Args:
        symbol: Stock ticker symbol
        filings: List of 8-K filing info dicts
        max_days: Time range used (for display)

    Returns:
        Formatted markdown string
    """
    if not filings:
        return f"No 8-K filings found for {symbol} in the last {max_days} days."

    lines = [
        f"# {symbol.upper()} 8-K Filings",
        "",
        f"> **{len(filings)} filings** found in the last {max_days} days.",
        "> Each filing below includes the date, items reported, and source URL.",
        "> **IMPORTANT:** When using information from these filings, always cite the source URL.",
        "",
    ]

    for i, filing in enumerate(filings, 1):
        lines.append("---")
        lines.append("")
        lines.append(f"## {i}. Filing: {filing['filing_date']}")
        lines.append("")
        lines.append(f"**Filing Date:** {filing['filing_date']}")
        lines.append(f"**CIK:** {filing['cik']}")
        lines.append(f"**Source:** {filing['source_url']}")
        lines.append("")

        # Items reported
        lines.append("### Items Reported")
        lines.append("")
        if filing["items_with_desc"]:
            for item_info in filing["items_with_desc"]:
                item = item_info["item"]
                desc = item_info["description"]
                if desc:
                    lines.append(f"- **{item}**: {desc}")
                else:
                    lines.append(f"- **{item}**")
        else:
            lines.append("- No items listed")
        lines.append("")

        # Press release content
        if filing["has_press_release"] and filing["press_release"]:
            lines.append("### Press Release")
            lines.append("")
            lines.append(filing["press_release"])
            lines.append("")
        else:
            lines.append("*No press release attached to this filing.*")
            lines.append("")

    return "\n".join(lines)


# ============================================================================
# Reminder functions (for 10-K/10-Q context)
# ============================================================================

def _find_recent_8k_filings_blocking(
    symbol: str,
    max_days: int = DEFAULT_8K_DAYS,
) -> List[Dict[str, Any]]:
    """
    Blocking implementation to find recent 8-K filings for reminder.

    Simplified version that doesn't fetch full press release content.
    """
    try:
        _init_edgar()
        from edgar import Company

        company = Company(symbol)
        filings_8k = company.get_filings(form="8-K")

        if not filings_8k or len(filings_8k) == 0:
            return []

        cutoff_date = date.today() - timedelta(days=max_days)

        filings = []
        for i in range(min(20, len(filings_8k))):
            try:
                filing = filings_8k.get_filing_at(i)

                if filing.filing_date < cutoff_date:
                    break

                obj = filing.obj()
                filing_items = obj.items if hasattr(obj, "items") else []

                filings.append({
                    "filing_date": filing.filing_date,
                    "items": filing_items,
                    "source_url": filing.filing_url,
                    "has_press_release": getattr(obj, "has_press_release", False),
                })

            except Exception as e:
                logger.debug(f"Error processing 8-K at index {i}: {e}")
                continue

        # Sort by filing date (most recent first)
        filings.sort(key=lambda x: x["filing_date"], reverse=True)
        return filings

    except Exception as e:
        logger.warning(f"Failed to find recent 8-K filings for {symbol}: {e}")
        return []


async def find_recent_8k_filings(
    symbol: str,
    max_days: int = DEFAULT_8K_DAYS,
) -> List[Dict[str, Any]]:
    """
    Async find recent 8-K filings for reminder display.

    Args:
        symbol: Stock ticker symbol
        max_days: Maximum days to look back (default: 90)

    Returns:
        List of 8-K filing info dicts (without full press release content)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _find_recent_8k_filings_blocking,
        symbol,
        max_days,
    )


def format_8k_reminder(
    recent_8ks: List[Dict[str, Any]],
    filing_type: str,
    max_days: int = DEFAULT_8K_DAYS,
) -> str:
    """
    Format a reminder about recent 8-K filings.

    Args:
        recent_8ks: List of recent 8-K filing info
        filing_type: The type of filing being viewed (10-K or 10-Q)
        max_days: Time range used (for display)

    Returns:
        Formatted markdown reminder section
    """
    if not recent_8ks:
        return ""

    from .types import FORM_8K_ITEMS

    lines = [
        "",
        "---",
        "",
        "## Recent 8-K Filings",
        "",
        f"> **{len(recent_8ks)} filings** found in the last {max_days} days.",
        "> These may contain material events, earnings announcements, or forward guidance.",
        "> Use `filing_type='8-K'` to fetch full 8-K content.",
        "",
    ]

    for filing in recent_8ks:
        filing_date = filing["filing_date"]
        has_pr = " (has press release)" if filing.get("has_press_release") else ""

        lines.append(f"### {filing_date}{has_pr}")
        lines.append("")

        # Items with descriptions
        for item in filing["items"]:
            desc = FORM_8K_ITEMS.get(item, "")
            if desc:
                lines.append(f"- **{item}**: {desc}")
            else:
                lines.append(f"- **{item}**")

        lines.append(f"- **URL:** {filing['source_url']}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Legacy compatibility (for nearby 8-K around a specific date)
# ============================================================================

async def find_nearby_8k_filings(
    symbol: str,
    filing_date: date,
    max_days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Find all 8-K filings within ±max_days of a filing date.

    Used to provide reminders about nearby 8-K filings when fetching 10-K/10-Q.

    Args:
        symbol: Stock ticker symbol
        filing_date: Reference date (e.g., 10-K or 10-Q filing date)
        max_days: Maximum days difference to consider

    Returns:
        List of dicts with: filing_date, items, source_url, days_diff
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _find_nearby_8k_filings_blocking,
        symbol,
        filing_date,
        max_days,
    )


def _find_nearby_8k_filings_blocking(
    symbol: str,
    filing_date: date,
    max_days: int,
) -> List[Dict[str, Any]]:
    """
    Blocking implementation for finding nearby 8-K filings.
    """
    try:
        _init_edgar()
        from edgar import Company

        company = Company(symbol)
        filings_8k = company.get_filings(form="8-K")

        if not filings_8k or len(filings_8k) == 0:
            return []

        nearby_filings = []

        for i in range(min(50, len(filings_8k))):
            try:
                filing = filings_8k.get_filing_at(i)
                diff = (filing.filing_date - filing_date).days

                # Check if within date range
                if abs(diff) > max_days:
                    # If we've gone past the date range, stop searching
                    if diff < -max_days:
                        break
                    continue

                obj = filing.obj()
                filing_items = obj.items if hasattr(obj, "items") else []

                nearby_filings.append({
                    "filing_date": filing.filing_date,
                    "items": filing_items,
                    "source_url": filing.filing_url,
                    "days_diff": diff,
                })

            except Exception as e:
                logger.debug(f"Error processing 8-K at index {i}: {e}")
                continue

        # Sort by filing date
        nearby_filings.sort(key=lambda x: x["filing_date"])
        return nearby_filings

    except Exception as e:
        logger.warning(f"Failed to find nearby 8-K filings for {symbol}: {e}")
        return []
