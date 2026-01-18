"""
Abstract base class for SEC filing parsers.

All parser implementations should inherit from BaseSECParser.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from ..types import SECSection, FilingType


class BaseSECParser(ABC):
    """Abstract base class for SEC filing parsers."""

    @abstractmethod
    def parse(
        self,
        html: str,
        filing_type: FilingType,
        sections: Optional[list[str]] = None,
    ) -> Dict[str, SECSection]:
        """
        Parse HTML content and extract sections.

        Args:
            html: Raw HTML content of the SEC filing
            filing_type: Type of filing (10-K or 10-Q)
            sections: Optional list of specific sections to extract.
                     If None, extracts all available sections.

        Returns:
            Dictionary mapping section keys to SECSection objects.
            Keys follow the standard naming convention:
            - 10-K: "item_1", "item_1a", "item_7", etc.
            - 10-Q: "part1_item1", "part1_item2", etc.
        """
        pass

    @abstractmethod
    def supports_filing_type(self, filing_type: FilingType) -> bool:
        """
        Check if this parser supports the given filing type.

        Args:
            filing_type: Type of filing to check

        Returns:
            True if the parser can handle this filing type
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this parser for logging purposes."""
        pass


class ParserError(Exception):
    """Base exception for parser errors."""

    pass


class ParsingFailedError(ParserError):
    """Raised when parsing fails completely."""

    pass


class SectionNotFoundError(ParserError):
    """Raised when a requested section cannot be found."""

    pass
