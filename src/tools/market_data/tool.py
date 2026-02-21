"""
LangChain tool wrappers for market data operations.

This module provides @tool decorated functions that serve as the LangChain interface.
The actual business logic is implemented in implementations.py.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from langchain_core.tools import tool

from .implementations import (
    fetch_company_overview,
    fetch_market_indices,
    fetch_sector_performance,
    fetch_stock_daily_prices,
    fetch_stock_screener,
)


@tool(response_format="content_and_artifact")
async def get_stock_daily_prices(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> Tuple[Union[List[Dict[str, Any]], str], Dict[str, Any]]:
    """
    Get stock daily OHLCV price data with smart normalization.
    Retrieves historical daily price data including open, high, low, close, volume.
    Supports US stocks, A-shares (Chinese), and HK stocks.

    **Smart Output Format:**
    - **Short periods (< 14 trading days)**: Returns raw list of daily OHLCV data
    - **Long periods (>= 14 trading days)**: Returns formatted summary report with:
      - Aggregated OHLC (period open/close/high/low)
      - Moving averages (20-day, 50-day, 200-day where applicable)
      - Volatility (daily standard deviation)
      - Volume statistics (average, total)
      - Period performance and price range

    Args:
        symbol: Stock ticker symbol
            - US: "AAPL", "MSFT", "GOOGL"
            - A-Share: "600519.SS" (Shanghai), "000858.SZ" (Shenzhen)
            - HK: "0700.HK" (Tencent), "9988.HK" (Alibaba)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        limit: Limit number of records (if not using date range)

    Returns:
        - If < 14 trading days: List of dictionaries with daily OHLCV data (newest first).
          Each record contains: symbol, date, open, high, low, close, volume,
          change, changePercent, vwap.
        - If >= 14 trading days: Formatted string report with aggregated statistics
          and performance metrics optimized for LLM interpretation.

    Example:
        # Get Apple stock last 10 days (returns raw list)
        aapl = get_stock_daily_prices("AAPL", limit=10)

        # Get Kweichow Moutai 1 year data (returns summary report)
        moutai = get_stock_daily_prices(
            "600519.SS",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )

        # Get Tencent 60 days (returns summary report with MAs and volatility)
        tencent = get_stock_daily_prices("0700.HK", limit=60)
    """
    content, artifact = await fetch_stock_daily_prices(
        symbol, start_date, end_date, limit
    )
    return content, artifact


@tool(response_format="content_and_artifact")
async def get_company_overview(
    symbol: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Get comprehensive investment analysis overview for a company.

    Retrieves and formats investment-relevant data including real-time quotes,
    financial health ratings, analyst consensus, earnings performance, and
    revenue segmentation. Data is presented in a human-readable format optimized
    for investment decision-making.

    Supports US stocks, A-shares (Chinese), and HK stocks.

    Args:
        symbol: Stock ticker symbol
            - US: "AAPL", "MSFT", "GOOGL"
            - A-Share: "600519.SS" (Shanghai), "000858.SZ" (Shenzhen)
            - HK: "0700.HK" (Tencent), "9988.HK" (Alibaba)

    Returns:
        Formatted string with comprehensive investment intelligence including:
        - Real-time quote (market status, price, day range, 52-week range, volume, after-hours)
        - Company basic information (name, sector, market cap, price)
        - Stock price performance (1D, 5D, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y returns)
        - Key financial metrics (valuation, profitability, leverage ratios)
        - SEC filing dates and next earnings report
        - Earnings performance (latest results vs estimates, surprises)
        - Analyst consensus (price targets, buy/sell recommendations, recent changes)
        - Revenue breakdown (by product line and geographic region)

    Example:
        # Get comprehensive investment overview for Apple
        overview = get_company_overview("AAPL")
        print(overview)  # Displays formatted investment intelligence

        # Get overview for Kweichow Moutai (A-share)
        moutai_overview = get_company_overview("600519.SS")

        # Get overview for Alibaba (HK)
        baba_overview = get_company_overview("9988.HK")
    """
    content, artifact = await fetch_company_overview(symbol)
    return content, artifact


@tool(response_format="content_and_artifact")
async def get_market_indices(
    indices: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 60,
) -> Tuple[Union[List[Dict[str, Any]], str], Dict[str, Any]]:
    """
    Get market indices data with smart normalization.

    Retrieves historical price data for major market indices (S&P 500, NASDAQ, Dow Jones).

    **Smart Output Format:**
    - **Short periods (< 14 trading days)**: Returns raw list of OHLCV data for all indices
    - **Long periods (>= 14 trading days)**: Returns formatted summary with separate sections per index:
      - Aggregated OHLC (period open/close/high/low)
      - Period performance and volatility
      - Moving averages (20-day, 50-day, 200-day where applicable)
      - Each index in its own section for easy comparison

    Args:
        indices: List of index symbols, default is major US indices
            - "^GSPC": S&P 500
            - "^IXIC": NASDAQ Composite
            - "^DJI": Dow Jones Industrial Average
            - "^RUT": Russell 2000
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        limit: Number of records per index (default 60)

    Returns:
        - If < 14 trading days: List of dictionaries with index OHLCV data (newest first)
        - If >= 14 trading days: Formatted string summary with statistics per index

    Example:
        # Get major indices last 10 days (returns raw list)
        indices = get_market_indices(limit=10)

        # Get major indices last 60 days (returns summary report)
        indices_summary = get_market_indices()

        # Get specific index with date range (returns summary)
        sp500_summary = get_market_indices(
            indices=["^GSPC"],
            start_date="2024-01-01",
            end_date="2024-12-31"
        )

        # Compare multiple indices over a year (returns summary with sections per index)
        market_comparison = get_market_indices(
            indices=["^GSPC", "^IXIC", "^DJI"],
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
    """
    content, artifact = await fetch_market_indices(indices, start_date, end_date, limit)
    return content, artifact


@tool(response_format="content_and_artifact")
async def get_sector_performance(
    date: Optional[str] = None,
) -> Tuple[Union[List[Dict[str, Any]], str], Dict[str, Any]]:
    """
    Get market sector performance.

    Retrieves sector performance metrics showing which sectors are
    outperforming or underperforming.

    Args:
        date: Analysis date in YYYY-MM-DD format (default: latest available)
            Note: Historical sector performance may not be available on all FMP plans

    Returns:
        List of dictionaries with sector performance data including:
        - sector: Sector name (e.g., "Technology", "Healthcare")
        - changesPercentage: Performance percentage (e.g., "1.50%")

    Available sectors typically include:
        - Basic Materials
        - Communication Services
        - Consumer Cyclical
        - Consumer Defensive
        - Energy
        - Financial Services
        - Healthcare
        - Industrials
        - Real Estate
        - Technology
        - Utilities

    Example:
        # Get current sector performance
        sectors = get_sector_performance()

        # Find best performing sector
        if sectors:
            best = max(sectors, key=lambda x: float(x.get('changesPercentage', '0%').rstrip('%')))
            print(f"Best sector: {best['sector']} at {best['changesPercentage']}")
    """
    content, artifact = await fetch_sector_performance(date)
    return content, artifact


@tool(response_format="content_and_artifact")
async def screen_stocks(
    market_cap_more_than: Optional[float] = None,
    market_cap_lower_than: Optional[float] = None,
    price_more_than: Optional[float] = None,
    price_lower_than: Optional[float] = None,
    volume_more_than: Optional[float] = None,
    volume_lower_than: Optional[float] = None,
    beta_more_than: Optional[float] = None,
    beta_lower_than: Optional[float] = None,
    dividend_more_than: Optional[float] = None,
    dividend_lower_than: Optional[float] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    is_etf: Optional[bool] = None,
    is_fund: Optional[bool] = None,
    is_actively_trading: Optional[bool] = None,
    limit: int = 50,
) -> Tuple[Union[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Screen stocks by market cap, price, volume, beta, sector, industry, exchange, and more.
    Uses the FMP Company Screener to filter stocks matching specified criteria.

    Args:
        market_cap_more_than: Minimum market capitalization (e.g., 1000000000 for $1B)
        market_cap_lower_than: Maximum market capitalization
        price_more_than: Minimum stock price
        price_lower_than: Maximum stock price
        volume_more_than: Minimum daily trading volume
        volume_lower_than: Maximum daily trading volume
        beta_more_than: Minimum beta value
        beta_lower_than: Maximum beta value
        dividend_more_than: Minimum dividend yield
        dividend_lower_than: Maximum dividend yield
        sector: Filter by sector (e.g., "Technology", "Healthcare", "Financial Services")
        industry: Filter by industry (e.g., "Software", "Biotechnology")
        exchange: Filter by exchange (e.g., "NASDAQ", "NYSE", "AMEX")
        country: Filter by country (e.g., "US", "CN", "GB")
        is_etf: Filter for ETFs only (True) or exclude ETFs (False)
        is_fund: Filter for funds only (True) or exclude funds (False)
        is_actively_trading: Filter for actively trading stocks only
        limit: Maximum number of results to return (default 50)

    Returns:
        Formatted markdown table with screener results and artifact for visualization.

    Example:
        # Find large-cap tech stocks
        screen_stocks(sector="Technology", market_cap_more_than=10000000000)

        # Find high-dividend stocks on NYSE
        screen_stocks(exchange="NYSE", dividend_more_than=4.0, limit=20)

        # Find low-beta value stocks
        screen_stocks(beta_lower_than=0.5, price_more_than=10, is_actively_trading=True)
    """
    content, artifact = await fetch_stock_screener(
        market_cap_more_than=market_cap_more_than,
        market_cap_lower_than=market_cap_lower_than,
        price_more_than=price_more_than,
        price_lower_than=price_lower_than,
        volume_more_than=volume_more_than,
        volume_lower_than=volume_lower_than,
        beta_more_than=beta_more_than,
        beta_lower_than=beta_lower_than,
        dividend_more_than=dividend_more_than,
        dividend_lower_than=dividend_lower_than,
        sector=sector,
        industry=industry,
        exchange=exchange,
        country=country,
        is_etf=is_etf,
        is_fund=is_fund,
        is_actively_trading=is_actively_trading,
        limit=limit,
    )
    return content, artifact
