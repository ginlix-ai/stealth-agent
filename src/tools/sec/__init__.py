"""
SEC Filing Tools.

Provides tools for fetching and parsing SEC filings (10-K, 10-Q).
Uses edgartools for direct SEC EDGAR access with structured extraction.

Example usage:
    from src.tools.sec import get_sec_filing

    # Get essential sections from latest 10-K (with financials)
    result = get_sec_filing("AAPL", "10-K")

    # Get all sections without financials
    result = get_sec_filing("AAPL", "10-K", use_defaults=False, include_financials=False)

    # Get specific sections
    result = get_sec_filing("AAPL", "10-K", sections=["item_1", "item_7"])

    # Access financial data
    print(result["financial_metrics"]["revenue"])
    print(result["financial_statements"]["income_statement"])
"""

from .tool import get_sec_filing
from .types import (
    FilingType,
    SECFiling,
    SECSection,
    SECFilingMetadata,
    FinancialStatements,
    FinancialMetrics,
    FORM_10K_SECTIONS,
    FORM_10Q_SECTIONS,
    FORM_10K_SECTION_DESCRIPTIONS,
    FORM_10Q_SECTION_DESCRIPTIONS,
    DEFAULT_10K_SECTIONS,
    DEFAULT_10Q_SECTIONS,
)

__all__ = [
    # Main tool
    "get_sec_filing",
    # Types
    "FilingType",
    "SECFiling",
    "SECSection",
    "SECFilingMetadata",
    "FinancialStatements",
    "FinancialMetrics",
    # Section mappings
    "FORM_10K_SECTIONS",
    "FORM_10Q_SECTIONS",
    "FORM_10K_SECTION_DESCRIPTIONS",
    "FORM_10Q_SECTION_DESCRIPTIONS",
    # Default sections
    "DEFAULT_10K_SECTIONS",
    "DEFAULT_10Q_SECTIONS",
]
