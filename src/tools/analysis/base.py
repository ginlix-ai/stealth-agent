"""
Base class for fundamental analysis tools.

Provides common functionality for data formatting, metadata generation,
error handling, and standardization across all fundamental analysis tools.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from abc import ABC, abstractmethod
import logging
import statistics

logger = logging.getLogger(__name__)


class FundamentalAnalysisBase(ABC):
    """Base class for all fundamental analysis tools"""

    def __init__(self, fmp_client):
        """
        Initialize base fundamental analysis tool

        Args:
            fmp_client: FMP API client instance
        """
        self.client = fmp_client

    @abstractmethod
    def analyze(
        self,
        symbol: str,
        period_type: str = "annual",
        lookback_periods: int = 5,
        detail_level: str = "compact"
    ) -> Dict[str, Any]:
        """
        Abstract method for analysis implementation

        Args:
            symbol: Stock ticker symbol
            period_type: 'annual' or 'quarterly'
            lookback_periods: Number of historical periods
            detail_level: 'compact' or 'extended'

        Returns:
            Dictionary with analysis results
        """
        pass

    def _format_decimal(self, value: Optional[Union[float, int]], decimals: int = 3) -> Optional[float]:
        """
        Format decimal to specified precision

        Args:
            value: Numeric value to format
            decimals: Number of decimal places

        Returns:
            Formatted value or None if input is None
        """
        if value is None:
            return None
        try:
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return None

    def _format_ratio(self, value: Optional[Union[float, int]]) -> Optional[float]:
        """Format ratio/percentage as decimal with 3 places"""
        return self._format_decimal(value, 3)

    def _format_large_number(self, value: Optional[Union[float, int]]) -> Optional[int]:
        """Format large numbers without decimals"""
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    def _format_per_share(self, value: Optional[Union[float, int]]) -> Optional[float]:
        """Format per-share values with 2 decimal places"""
        return self._format_decimal(value, 2)

    def _safe_divide(self, numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        """
        Safely divide two numbers, returning None if invalid

        Args:
            numerator: Top number
            denominator: Bottom number

        Returns:
            Division result or None
        """
        if numerator is None or denominator is None or denominator == 0:
            return None
        try:
            return float(numerator) / float(denominator)
        except (TypeError, ValueError):
            return None

    def _calculate_growth_rate(self, current: Optional[float], previous: Optional[float]) -> Optional[float]:
        """
        Calculate growth rate between two periods

        Args:
            current: Current period value
            previous: Previous period value

        Returns:
            Growth rate as decimal or None
        """
        return self._safe_divide(
            (current - previous) if current is not None and previous is not None else None,
            abs(previous) if previous is not None else None
        )

    def _calculate_cagr(self, end_value: float, start_value: float, years: int) -> Optional[float]:
        """
        Calculate compound annual growth rate

        Args:
            end_value: Ending value
            start_value: Starting value
            years: Number of years

        Returns:
            CAGR as decimal or None
        """
        if start_value is None or end_value is None or years is None:
            return None
        if start_value <= 0 or end_value <= 0 or years <= 0:
            return None
        try:
            return pow(end_value / start_value, 1.0 / years) - 1
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def _calculate_statistics(self, values: List[float]) -> Dict[str, Optional[float]]:
        """
        Calculate basic statistics for a list of values

        Args:
            values: List of numeric values

        Returns:
            Dictionary with mean, median, std_dev
        """
        clean_values = [v for v in values if v is not None]

        if not clean_values:
            return {
                "mean": None,
                "median": None,
                "std_dev": None,
                "min": None,
                "max": None
            }

        return {
            "mean": self._format_decimal(statistics.mean(clean_values)),
            "median": self._format_decimal(statistics.median(clean_values)),
            "std_dev": self._format_decimal(statistics.stdev(clean_values)) if len(clean_values) > 1 else None,
            "min": self._format_decimal(min(clean_values)),
            "max": self._format_decimal(max(clean_values))
        }

    def _generate_metadata(
        self,
        symbol: str,
        period_type: str,
        lookback_years: int,
        latest_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate standard metadata for analysis results

        Args:
            symbol: Stock ticker
            period_type: Analysis period type
            lookback_years: Number of years analyzed
            latest_date: Most recent data date

        Returns:
            Metadata dictionary
        """
        return {
            "symbol": symbol,
            "as_of": latest_date or datetime.now().strftime("%Y-%m-%d"),
            "basis": period_type,
            "lookback_years": lookback_years,
            "data_source": "fmp"
        }

    def _extract_flags(
        self,
        conditions: Dict[str, bool],
        max_flags: int = 5
    ) -> List[str]:
        """
        Extract flags based on conditions

        Args:
            conditions: Dictionary of flag_name: condition pairs
            max_flags: Maximum number of flags to return

        Returns:
            List of flag strings
        """
        flags = []
        for flag_name, condition in conditions.items():
            if condition and len(flags) < max_flags:
                flags.append(flag_name)
        return flags

    def _get_latest_value(self, data_list: List[Dict], field: str) -> Optional[Any]:
        """
        Get the latest (most recent) value from a list of period data

        Args:
            data_list: List of dictionaries with period data
            field: Field name to extract

        Returns:
            Latest value or None
        """
        if not data_list:
            return None
        return data_list[0].get(field)

    def _calculate_trend(self, values: List[float], min_periods: int = 3) -> Optional[str]:
        """
        Determine trend direction from values

        Args:
            values: List of values (newest to oldest)
            min_periods: Minimum periods needed

        Returns:
            'increasing', 'decreasing', 'stable', or None
        """
        clean_values = [v for v in values if v is not None]

        if len(clean_values) < min_periods:
            return None

        # Simple linear trend
        recent = clean_values[:min_periods]
        if all(recent[i] >= recent[i+1] * 0.98 for i in range(len(recent)-1)):
            return "increasing"
        elif all(recent[i] <= recent[i+1] * 1.02 for i in range(len(recent)-1)):
            return "decreasing"
        else:
            return "stable"

    def _handle_optional_field(
        self,
        value: Any,
        condition: bool = True
    ) -> Optional[Any]:
        """
        Handle optional fields that may not be available

        Args:
            value: Field value
            condition: Whether field should be included

        Returns:
            Value if condition is met, None otherwise
        """
        return value if condition and value is not None else None
