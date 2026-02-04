"""
Data Agent Tools - Market data retrieval and analysis tools.

Provides comprehensive market data tools supporting US stocks, A-shares (Chinese),
and HK stocks. Tools are organized with clear separation between LangChain interface
(@tool decorators) and business logic implementations.

Available tools:
- get_stock_daily_prices: Historical daily OHLCV price data
- get_company_overview: Comprehensive investment intelligence overview (includes real-time quote)
- get_market_indices: Market indices data (S&P 500, NASDAQ, Dow Jones)
- get_sector_performance: Sector performance metrics
"""

from .tool import (
    get_stock_daily_prices,
    get_company_overview,
    get_market_indices,
    get_sector_performance,
)

__all__ = [
    "get_stock_daily_prices",
    "get_company_overview",
    "get_market_indices",
    "get_sector_performance",
]
