"""
Type definitions for SEC filing tools.

Contains enums, section mappings, and Pydantic models for SEC filings.
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel


class FilingType(str, Enum):
    """Supported SEC filing types."""

    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"


# 8-K Item descriptions (common items)
FORM_8K_ITEMS: Dict[str, str] = {
    "Item 1.01": "Entry into a Material Definitive Agreement",
    "Item 1.02": "Termination of a Material Definitive Agreement",
    "Item 1.03": "Bankruptcy or Receivership",
    "Item 2.01": "Completion of Acquisition or Disposition of Assets",
    "Item 2.02": "Results of Operations and Financial Condition",  # Earnings
    "Item 2.03": "Creation of a Direct Financial Obligation",
    "Item 2.04": "Triggering Events That Accelerate Obligations",
    "Item 2.05": "Costs Associated with Exit or Disposal Activities",
    "Item 2.06": "Material Impairments",
    "Item 3.01": "Notice of Delisting or Failure to Satisfy Listing Rule",
    "Item 3.02": "Unregistered Sales of Equity Securities",
    "Item 3.03": "Material Modification to Rights of Security Holders",
    "Item 4.01": "Changes in Registrant's Certifying Accountant",
    "Item 4.02": "Non-Reliance on Previously Issued Financial Statements",
    "Item 5.01": "Changes in Control of Registrant",
    "Item 5.02": "Departure/Election of Directors or Officers",
    "Item 5.03": "Amendments to Articles of Incorporation or Bylaws",
    "Item 5.04": "Temporary Suspension of Trading Under Employee Plans",
    "Item 5.05": "Amendment to Code of Ethics",
    "Item 5.06": "Change in Shell Company Status",
    "Item 5.07": "Submission of Matters to a Vote of Security Holders",
    "Item 5.08": "Shareholder Nominations",
    "Item 6.01": "ABS Informational and Computational Material",
    "Item 6.02": "Change of Servicer or Trustee",
    "Item 6.03": "Change in Credit Enhancement",
    "Item 6.04": "Failure to Make a Required Distribution",
    "Item 6.05": "Securities Act Updating Disclosure",
    "Item 7.01": "Regulation FD Disclosure",  # Forward guidance
    "Item 8.01": "Other Events",
    "Item 9.01": "Financial Statements and Exhibits",
}


# Standard section mappings for 10-K filings (SEC Regulation S-K)
FORM_10K_SECTIONS: Dict[str, str] = {
    # Part I
    "item_1": "Item 1",  # Business
    "item_1a": "Item 1A",  # Risk Factors
    "item_1b": "Item 1B",  # Unresolved Staff Comments
    "item_1c": "Item 1C",  # Cybersecurity
    "item_2": "Item 2",  # Properties
    "item_3": "Item 3",  # Legal Proceedings
    "item_4": "Item 4",  # Mine Safety Disclosures
    # Part II
    "item_5": "Item 5",  # Market for Common Equity
    "item_6": "Item 6",  # [Reserved]
    "item_7": "Item 7",  # MD&A
    "item_7a": "Item 7A",  # Quantitative Disclosures About Market Risk
    "item_8": "Item 8",  # Financial Statements
    "item_9": "Item 9",  # Changes in Accountants
    "item_9a": "Item 9A",  # Controls and Procedures
    "item_9b": "Item 9B",  # Other Information
    "item_9c": "Item 9C",  # Disclosure re Foreign Jurisdictions
    # Part III
    "item_10": "Item 10",  # Directors and Officers
    "item_11": "Item 11",  # Executive Compensation
    "item_12": "Item 12",  # Security Ownership
    "item_13": "Item 13",  # Related Transactions
    "item_14": "Item 14",  # Principal Accountant Fees
    # Part IV
    "item_15": "Item 15",  # Exhibits and Financial Schedules
    "item_16": "Item 16",  # Form 10-K Summary
}

# Section descriptions for 10-K
FORM_10K_SECTION_DESCRIPTIONS: Dict[str, str] = {
    "item_1": "Business description, products, and services",
    "item_1a": "Risk factors that could affect the company",
    "item_1b": "Unresolved SEC staff comments",
    "item_1c": "Cybersecurity risk management and governance",
    "item_2": "Company properties and facilities",
    "item_3": "Legal proceedings and litigation",
    "item_4": "Mine safety disclosures (if applicable)",
    "item_5": "Market for common equity and stockholder matters",
    "item_6": "[Reserved]",
    "item_7": "Management's Discussion and Analysis (MD&A)",
    "item_7a": "Quantitative and qualitative market risk disclosures",
    "item_8": "Financial statements and supplementary data",
    "item_9": "Changes in and disagreements with accountants",
    "item_9a": "Controls and procedures",
    "item_9b": "Other information",
    "item_9c": "Foreign jurisdiction disclosure",
    "item_10": "Directors, executive officers, and corporate governance",
    "item_11": "Executive compensation",
    "item_12": "Security ownership of beneficial owners and management",
    "item_13": "Certain relationships and related transactions",
    "item_14": "Principal accountant fees and services",
    "item_15": "Exhibits and financial statement schedules",
    "item_16": "Form 10-K summary",
}

# Standard section mappings for 10-Q filings
FORM_10Q_SECTIONS: Dict[str, str] = {
    # Part I - Financial Information
    "part1_item1": "Item 1",  # Financial Statements
    "part1_item2": "Item 2",  # MD&A
    "part1_item3": "Item 3",  # Quantitative and Qualitative Disclosures About Market Risk
    "part1_item4": "Item 4",  # Controls and Procedures
    # Part II - Other Information
    "part2_item1": "Item 1",  # Legal Proceedings
    "part2_item1a": "Item 1A",  # Risk Factors
    "part2_item2": "Item 2",  # Unregistered Sales of Equity Securities
    "part2_item3": "Item 3",  # Defaults Upon Senior Securities
    "part2_item4": "Item 4",  # Mine Safety Disclosures
    "part2_item5": "Item 5",  # Other Information
    "part2_item6": "Item 6",  # Exhibits
}

# Section descriptions for 10-Q
FORM_10Q_SECTION_DESCRIPTIONS: Dict[str, str] = {
    "part1_item1": "Quarterly financial statements (unaudited)",
    "part1_item2": "Management's Discussion and Analysis (MD&A)",
    "part1_item3": "Quantitative and qualitative market risk disclosures",
    "part1_item4": "Controls and procedures",
    "part2_item1": "Legal proceedings updates",
    "part2_item1a": "Risk factors updates",
    "part2_item2": "Unregistered sales of equity securities",
    "part2_item3": "Defaults upon senior securities",
    "part2_item4": "Mine safety disclosures",
    "part2_item5": "Other information",
    "part2_item6": "Exhibits",
}

# Default sections to extract (essential for financial analysis)
DEFAULT_10K_SECTIONS = ["item_1", "item_1a", "item_7", "item_8"]
DEFAULT_10Q_SECTIONS = ["part1_item2", "part2_item1a"]  # MD&A + Risk Factors


class SECSection(BaseModel):
    """A single section from an SEC filing."""

    title: str
    content: str
    length: int

    @classmethod
    def from_content(cls, title: str, content: str) -> "SECSection":
        """Create a section from title and content."""
        return cls(title=title, content=content, length=len(content))


class SECFiling(BaseModel):
    """Parsed SEC filing with metadata and sections."""

    symbol: str
    filing_type: FilingType
    filing_date: str
    period_end: Optional[str] = None
    cik: Optional[str] = None
    source_url: Optional[str] = None
    sections: Dict[str, SECSection]

    @property
    def total_content_length(self) -> int:
        """Total length of all section content."""
        return sum(section.length for section in self.sections.values())


class SECFilingMetadata(BaseModel):
    """Metadata about an SEC filing from FMP API."""

    symbol: str
    filing_date: str
    accepted_date: str
    cik: str
    filing_type: str
    index_url: str  # Link to filing index page
    document_url: str  # Link to actual document (finalLink)


class FinancialStatements(BaseModel):
    """Financial statements from SEC filing."""

    balance_sheet: Optional[str] = None
    income_statement: Optional[str] = None
    cash_flow_statement: Optional[str] = None


class FinancialMetrics(BaseModel):
    """Key financial metrics extracted from SEC filing."""

    revenue: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    stockholders_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capital_expenditures: Optional[float] = None
    free_cash_flow: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_assets: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "FinancialMetrics":
        """Create from dictionary, filtering to known fields."""
        known_fields = cls.model_fields.keys()
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
