"""Timezone utilities for label extraction and formatting."""

from datetime import datetime
from typing import Optional


def get_timezone_label(dt: Optional[datetime]) -> str:
    """
    Extract timezone abbreviation from a datetime object.

    Uses strftime('%Z') to get DST-aware abbreviations like:
    - EST/EDT for America/New_York
    - CST for Asia/Shanghai
    - UTC for UTC timezone

    Args:
        dt: Timezone-aware datetime object (or None)

    Returns:
        Timezone abbreviation string (e.g., "EST", "EDT", "CST", "UTC")
        Returns "UTC" if dt is None or naive (no timezone info)

    Example:
        >>> from datetime import datetime
        >>> from zoneinfo import ZoneInfo
        >>> dt_winter = datetime(2025, 1, 15, tzinfo=ZoneInfo("America/New_York"))
        >>> get_timezone_label(dt_winter)
        'EST'
        >>> dt_summer = datetime(2025, 7, 15, tzinfo=ZoneInfo("America/New_York"))
        >>> get_timezone_label(dt_summer)
        'EDT'
    """
    if dt is None or dt.tzinfo is None:
        # Naive datetime or None - default to UTC
        return "UTC"

    # Extract timezone abbreviation (DST-aware)
    return dt.strftime('%Z')
