"""
SEC filing parsers.

Provides parser implementations for extracting sections from SEC filings.
"""

from .base import BaseSECParser, ParserError, ParsingFailedError, SectionNotFoundError
from .edgartools_parser import EdgarToolsParser
from .crawl4ai_parser import Crawl4AIParser

__all__ = [
    # Base classes
    "BaseSECParser",
    "ParserError",
    "ParsingFailedError",
    "SectionNotFoundError",
    # Implementations
    "EdgarToolsParser",  # Primary parser (direct SEC access)
    "Crawl4AIParser",  # Fallback: regex-based extraction
]
