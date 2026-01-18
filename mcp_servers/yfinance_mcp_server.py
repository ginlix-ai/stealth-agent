#!/usr/bin/env python3
"""
Yahoo Finance MCP Server - Self-contained MCP server for financial data
Provides tools to fetch stock prices, financial statements, options, and company data

This server is designed to showcase PTC (Programmatic Tool Calling) value by returning
large amounts of structured data that benefits from programmatic tool calling.

Usage:
    python yfinance_mcp_server.py

For LangGraph integration, configure this as an MCP server with stdio transport.
"""

from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import yfinance as yf
import json
from datetime import datetime

# Create the MCP server
mcp = FastMCP("YahooFinanceMCP")


def _serialize_dataframe(df) -> dict:
    """Convert pandas DataFrame to JSON-serializable dict, handling NaN values.

    For financial statements (metrics as rows, dates as columns), returns:
    {metric_name: {date: value, ...}, ...}
    """
    import pandas as pd

    if df is None or df.empty:
        return {}

    df = df.copy()

    # Convert DatetimeIndex in index to string
    if isinstance(df.index, pd.DatetimeIndex):
        df.index = df.index.strftime('%Y-%m-%d')

    # Convert DatetimeIndex in columns to string (common for financial statements)
    if isinstance(df.columns, pd.DatetimeIndex):
        df.columns = df.columns.strftime('%Y-%m-%d')

    # Use 'index' orient: {row_label: {col_label: value}}
    # This gives {metric: {date: value}} for financial statements
    return json.loads(df.fillna("N/A").to_json(orient="index"))


def _serialize_history(df) -> list:
    """Convert historical price DataFrame to list of record dicts.

    Returns:
        List of dicts, each with keys: date, open, high, low, close, volume
        (plus dividends, splits if present). Empty list if no data.

    Example record:
        {"date": "2024-01-01", "open": 150.0, "high": 151.5, "low": 149.0,
         "close": 151.0, "volume": 1000000}
    """
    if df is None or df.empty:
        return []

    df = df.copy()
    records = []

    for idx, row in df.iterrows():
        record = {
            "date": idx.strftime('%Y-%m-%d'),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        }
        if "Dividends" in df.columns:
            record["dividends"] = round(float(row["Dividends"]), 4)
        if "Stock Splits" in df.columns:
            record["splits"] = float(row["Stock Splits"])
        records.append(record)

    return records


# ============================================================================
# SINGLE TICKER TOOLS
# ============================================================================

@mcp.tool()
def get_stock_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d"
) -> dict:
    """
    Get historical OHLCV (Open, High, Low, Close, Volume) data for a stock.

    HIGH PTC VALUE: Returns 252 rows per year of daily data - ideal for calculating
    returns, volatility, moving averages, and technical indicators in code.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT", "TSLA")
        period: Data period - 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: Data interval - 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo

    Returns:
        dict: {
            "ticker": str,
            "period": str,
            "interval": str,
            "count": int,
            "history": list[dict]  # Each dict has: date, open, high, low, close, volume
        }
        Use pd.DataFrame(result["history"]) to convert to DataFrame.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        if hist.empty:
            return {"error": f"No data found for ticker {ticker}"}
        history = _serialize_history(hist)
        return {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        return {"error": f"Failed to fetch history for {ticker}: {str(e)}"}


@mcp.tool()
def get_income_statement(ticker: str, quarterly: bool = True) -> dict:
    """
    Get income statement data (revenue, expenses, net income, etc.)

    HIGH PTC VALUE: Returns 4 quarters (or 4 years) of 30+ financial line items.
    Ideal for calculating profit margins, revenue growth, and profitability trends.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        quarterly: If True, returns quarterly data; if False, returns annual data

    Returns:
        Dictionary with income statement data indexed by date
    """
    try:
        stock = yf.Ticker(ticker)
        if quarterly:
            df = stock.quarterly_income_stmt
        else:
            df = stock.income_stmt
        if df is None or df.empty:
            return {"error": f"No income statement data for {ticker}"}
        return {"ticker": ticker, "quarterly": quarterly, "data": _serialize_dataframe(df)}
    except Exception as e:
        return {"error": f"Failed to fetch income statement for {ticker}: {str(e)}"}


@mcp.tool()
def get_balance_sheet(ticker: str, quarterly: bool = True) -> dict:
    """
    Get balance sheet data (assets, liabilities, equity).

    HIGH PTC VALUE: Returns 4 quarters (or 4 years) of asset/liability data.
    Ideal for calculating debt ratios, current ratio, book value, and solvency metrics.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        quarterly: If True, returns quarterly data; if False, returns annual data

    Returns:
        Dictionary with balance sheet data indexed by date
    """
    try:
        stock = yf.Ticker(ticker)
        if quarterly:
            df = stock.quarterly_balance_sheet
        else:
            df = stock.balance_sheet
        if df is None or df.empty:
            return {"error": f"No balance sheet data for {ticker}"}
        return {"ticker": ticker, "quarterly": quarterly, "data": _serialize_dataframe(df)}
    except Exception as e:
        return {"error": f"Failed to fetch balance sheet for {ticker}: {str(e)}"}


@mcp.tool()
def get_cash_flow(ticker: str, quarterly: bool = True) -> dict:
    """
    Get cash flow statement data (operating, investing, financing activities).

    HIGH PTC VALUE: Returns 4 quarters (or 4 years) of cash flow data.
    Ideal for calculating free cash flow, cash conversion, and capital allocation.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        quarterly: If True, returns quarterly data; if False, returns annual data

    Returns:
        Dictionary with cash flow statement data indexed by date
    """
    try:
        stock = yf.Ticker(ticker)
        if quarterly:
            df = stock.quarterly_cashflow
        else:
            df = stock.cashflow
        if df is None or df.empty:
            return {"error": f"No cash flow data for {ticker}"}
        return {"ticker": ticker, "quarterly": quarterly, "data": _serialize_dataframe(df)}
    except Exception as e:
        return {"error": f"Failed to fetch cash flow for {ticker}: {str(e)}"}


@mcp.tool()
def get_options_chain(ticker: str, expiration: Optional[str] = None) -> dict:
    """
    Get options chain (calls and puts) for a stock.

    VERY HIGH PTC VALUE: Returns 100-300 option contracts per expiration.
    Ideal for filtering by strike, calculating Greeks, finding opportunities,
    and analyzing implied volatility surface.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        expiration: Option expiration date (YYYY-MM-DD). If None, uses nearest expiration.

    Returns:
        Dictionary with calls and puts DataFrames, plus available expirations
    """
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return {"error": f"No options data available for {ticker}"}

        # Use specified expiration or default to nearest
        if expiration and expiration in expirations:
            exp_date = expiration
        else:
            exp_date = expirations[0]

        opt = stock.option_chain(exp_date)

        # Serialize options data
        calls = opt.calls.to_dict(orient='records') if not opt.calls.empty else []
        puts = opt.puts.to_dict(orient='records') if not opt.puts.empty else []

        # Clean up timestamp fields
        for contract in calls + puts:
            for key, value in contract.items():
                if hasattr(value, 'isoformat'):
                    contract[key] = value.isoformat()
                elif isinstance(value, float) and value != value:  # NaN check
                    contract[key] = None

        return {
            "ticker": ticker,
            "expiration": exp_date,
            "available_expirations": list(expirations),
            "calls": calls,
            "puts": puts,
            "num_calls": len(calls),
            "num_puts": len(puts)
        }
    except Exception as e:
        return {"error": f"Failed to fetch options for {ticker}: {str(e)}"}


@mcp.tool()
def get_company_info(ticker: str) -> dict:
    """
    Get comprehensive company information (sector, industry, market cap, ratios, etc.)

    MEDIUM PTC VALUE: Returns 100+ fields of company metadata.
    Useful for screening, sector analysis, and fundamental overview.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        Dictionary with company information
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info:
            return {"error": f"No company info for {ticker}"}

        # Clean up info dict - remove None values and convert timestamps
        cleaned = {}
        for key, value in info.items():
            if value is None:
                continue
            if hasattr(value, 'isoformat'):
                cleaned[key] = value.isoformat()
            else:
                cleaned[key] = value

        return {"ticker": ticker, "info": cleaned}
    except Exception as e:
        return {"error": f"Failed to fetch company info for {ticker}: {str(e)}"}


@mcp.tool()
def get_analyst_recommendations(ticker: str) -> dict:
    """
    Get analyst recommendations history (buy/hold/sell ratings over time).

    MEDIUM PTC VALUE: Returns 50+ historical recommendations.
    Useful for sentiment analysis, consensus tracking, and rating changes.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        Dictionary with analyst recommendations history
    """
    try:
        stock = yf.Ticker(ticker)
        recs = stock.recommendations
        if recs is None or recs.empty:
            return {"error": f"No analyst recommendations for {ticker}"}

        # Convert to records format
        recs = recs.reset_index()
        records = recs.to_dict(orient='records')

        # Clean up timestamps
        for rec in records:
            for key, value in rec.items():
                if hasattr(value, 'isoformat'):
                    rec[key] = value.isoformat()

        return {"ticker": ticker, "recommendations": records, "count": len(records)}
    except Exception as e:
        return {"error": f"Failed to fetch recommendations for {ticker}: {str(e)}"}


@mcp.tool()
def get_institutional_holders(ticker: str) -> dict:
    """
    Get list of institutional holders and their positions.

    MEDIUM PTC VALUE: Returns top institutional shareholders.
    Useful for ownership analysis and identifying major stakeholders.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        Dictionary with institutional holders data
    """
    try:
        stock = yf.Ticker(ticker)
        holders = stock.institutional_holders
        if holders is None or holders.empty:
            return {"error": f"No institutional holder data for {ticker}"}

        records = holders.to_dict(orient='records')

        # Clean up dates and NaN values
        for holder in records:
            for key, value in holder.items():
                if hasattr(value, 'isoformat'):
                    holder[key] = value.isoformat()
                elif isinstance(value, float) and value != value:  # NaN
                    holder[key] = None

        return {"ticker": ticker, "holders": records, "count": len(records)}
    except Exception as e:
        return {"error": f"Failed to fetch institutional holders for {ticker}: {str(e)}"}


@mcp.tool()
def get_dividends_and_splits(ticker: str) -> dict:
    """
    Get dividend payment history and stock split events.

    HIGH PTC VALUE: Returns years of dividend/split history for total return
    calculations, dividend growth analysis, and split-adjusted price computations.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "dividends": list[dict],  # Each: {date, amount}
            "splits": list[dict],     # Each: {date, ratio}
            "dividend_count": int,
            "split_count": int
        }
    """
    try:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        splits = stock.splits

        # Convert dividends Series to records
        dividend_records = []
        if dividends is not None and not dividends.empty:
            for date, amount in dividends.items():
                dividend_records.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "amount": round(float(amount), 4)
                })

        # Convert splits Series to records
        split_records = []
        if splits is not None and not splits.empty:
            for date, ratio in splits.items():
                split_records.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "ratio": float(ratio)
                })

        return {
            "ticker": ticker,
            "dividends": dividend_records,
            "splits": split_records,
            "dividend_count": len(dividend_records),
            "split_count": len(split_records)
        }
    except Exception as e:
        return {"error": f"Failed to fetch dividends/splits for {ticker}: {str(e)}"}


@mcp.tool()
def get_earnings_data(ticker: str, quarterly: bool = True) -> dict:
    """
    Get historical earnings (EPS) and revenue data.

    HIGH PTC VALUE: Returns multiple quarters/years of earnings data for
    trend analysis, earnings growth calculations, and valuation modeling.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        quarterly: If True, returns quarterly data; if False, returns annual data

    Returns:
        dict: {
            "ticker": str,
            "quarterly": bool,
            "count": int,
            "earnings": list[dict]  # Each: {date, revenue, earnings}
        }
    """
    try:
        stock = yf.Ticker(ticker)
        if quarterly:
            earnings = stock.quarterly_earnings
        else:
            earnings = stock.earnings

        if earnings is None or earnings.empty:
            return {"error": f"No earnings data for {ticker}"}

        # Convert to records
        earnings = earnings.reset_index()
        records = []
        for _, row in earnings.iterrows():
            record = {}
            for col in earnings.columns:
                val = row[col]
                if hasattr(val, 'strftime'):
                    record[col.lower().replace(' ', '_')] = val.strftime('%Y-%m-%d')
                elif hasattr(val, 'isoformat'):
                    record[col.lower().replace(' ', '_')] = val.isoformat()
                elif isinstance(val, float) and val != val:  # NaN
                    record[col.lower().replace(' ', '_')] = None
                else:
                    record[col.lower().replace(' ', '_')] = val
            records.append(record)

        return {
            "ticker": ticker,
            "quarterly": quarterly,
            "count": len(records),
            "earnings": records
        }
    except Exception as e:
        return {"error": f"Failed to fetch earnings for {ticker}: {str(e)}"}


@mcp.tool()
def get_earnings_dates(ticker: str) -> dict:
    """
    Get earnings announcement dates with EPS estimates vs actuals.

    HIGH PTC VALUE: Returns earnings calendar with surprise data for
    event-driven analysis and earnings surprise tracking.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "count": int,
            "earnings_dates": list[dict]  # Each: {date, eps_estimate, reported_eps, surprise_pct}
        }
    """
    try:
        stock = yf.Ticker(ticker)
        dates = stock.earnings_dates

        if dates is None or dates.empty:
            return {"error": f"No earnings dates for {ticker}"}

        # Convert to records
        dates = dates.reset_index()
        records = []
        for _, row in dates.iterrows():
            record = {}
            for col in dates.columns:
                val = row[col]
                col_name = col.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('%', 'pct')
                if hasattr(val, 'strftime'):
                    record[col_name] = val.strftime('%Y-%m-%d %H:%M:%S')
                elif hasattr(val, 'isoformat'):
                    record[col_name] = val.isoformat()
                elif isinstance(val, float) and val != val:  # NaN
                    record[col_name] = None
                else:
                    record[col_name] = val
            records.append(record)

        return {
            "ticker": ticker,
            "count": len(records),
            "earnings_dates": records
        }
    except Exception as e:
        return {"error": f"Failed to fetch earnings dates for {ticker}: {str(e)}"}


@mcp.tool()
def get_insider_transactions(ticker: str) -> dict:
    """
    Get insider buying and selling activity.

    HIGH PTC VALUE: Returns insider transactions for sentiment analysis,
    identifying unusual activity, and tracking executive confidence.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "count": int,
            "transactions": list[dict]  # Each: {insider, relation, date, transaction, shares, value}
        }
    """
    try:
        stock = yf.Ticker(ticker)
        transactions = stock.insider_transactions

        if transactions is None or transactions.empty:
            return {"error": f"No insider transactions for {ticker}"}

        records = transactions.to_dict(orient='records')

        # Clean up dates and NaN values
        for rec in records:
            for key, value in list(rec.items()):
                new_key = key.lower().replace(' ', '_')
                if new_key != key:
                    rec[new_key] = rec.pop(key)
                    value = rec[new_key]
                if hasattr(value, 'isoformat'):
                    rec[new_key] = value.isoformat()
                elif isinstance(value, float) and value != value:  # NaN
                    rec[new_key] = None

        return {
            "ticker": ticker,
            "count": len(records),
            "transactions": records
        }
    except Exception as e:
        return {"error": f"Failed to fetch insider transactions for {ticker}: {str(e)}"}


@mcp.tool()
def get_mutualfund_holders(ticker: str) -> dict:
    """
    Get top mutual fund holders and their positions.

    MEDIUM PTC VALUE: Returns top mutual funds holding the stock.
    Complements institutional holders for complete ownership picture.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "count": int,
            "holders": list[dict]  # Each: {holder, shares, date_reported, pct_held, value}
        }
    """
    try:
        stock = yf.Ticker(ticker)
        holders = stock.mutualfund_holders

        if holders is None or holders.empty:
            return {"error": f"No mutual fund holder data for {ticker}"}

        records = holders.to_dict(orient='records')

        # Clean up dates and NaN values
        for rec in records:
            for key, value in list(rec.items()):
                new_key = key.lower().replace(' ', '_').replace('%', 'pct')
                if new_key != key:
                    rec[new_key] = rec.pop(key)
                    value = rec[new_key]
                if hasattr(value, 'isoformat'):
                    rec[new_key] = value.isoformat()
                elif isinstance(value, float) and value != value:  # NaN
                    rec[new_key] = None

        return {"ticker": ticker, "count": len(records), "holders": records}
    except Exception as e:
        return {"error": f"Failed to fetch mutual fund holders for {ticker}: {str(e)}"}


@mcp.tool()
def get_sustainability_data(ticker: str) -> dict:
    """
    Get ESG (Environmental, Social, Governance) scores and sustainability metrics.

    MEDIUM PTC VALUE: Returns ESG scores for sustainable investing analysis,
    portfolio screening, and corporate responsibility evaluation.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "scores": dict  # ESG metrics including environment, social, governance scores
        }
    """
    try:
        stock = yf.Ticker(ticker)
        sustainability = stock.sustainability

        if sustainability is None or sustainability.empty:
            return {"error": f"No sustainability data for {ticker}"}

        # Convert DataFrame to dict (sustainability is indexed by metric name)
        scores = {}
        for idx in sustainability.index:
            val = sustainability.loc[idx].values[0] if len(sustainability.loc[idx].values) > 0 else None
            key = str(idx).lower().replace(' ', '_')
            if isinstance(val, float) and val != val:  # NaN
                scores[key] = None
            else:
                scores[key] = val

        return {"ticker": ticker, "scores": scores}
    except Exception as e:
        return {"error": f"Failed to fetch sustainability data for {ticker}: {str(e)}"}


@mcp.tool()
def get_news(ticker: str) -> dict:
    """
    Get recent news articles for a stock.

    MEDIUM PTC VALUE: Returns recent news headlines and links for
    sentiment analysis, event tracking, and market context.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "count": int,
            "news": list[dict]  # Each: {title, publisher, link, publish_time, type}
        }
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        if news is None or len(news) == 0:
            return {"error": f"No news for {ticker}"}

        # Clean up news items
        cleaned_news = []
        for item in news:
            cleaned_item = {
                "title": item.get("title"),
                "publisher": item.get("publisher"),
                "link": item.get("link"),
                "publish_time": item.get("providerPublishTime"),
                "type": item.get("type"),
            }
            # Convert timestamp to ISO format if present
            if cleaned_item["publish_time"]:
                from datetime import datetime
                cleaned_item["publish_time"] = datetime.fromtimestamp(
                    cleaned_item["publish_time"]
                ).isoformat()
            cleaned_news.append(cleaned_item)

        return {"ticker": ticker, "count": len(cleaned_news), "news": cleaned_news}
    except Exception as e:
        return {"error": f"Failed to fetch news for {ticker}: {str(e)}"}


@mcp.tool()
def get_insider_roster(ticker: str) -> dict:
    """
    Get list of key insiders and their current holdings.

    MEDIUM PTC VALUE: Returns insider roster with positions and share counts
    for identifying key decision-makers and their stake in the company.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")

    Returns:
        dict: {
            "ticker": str,
            "count": int,
            "insiders": list[dict]  # Each: {name, position, shares, latest_transaction}
        }
    """
    try:
        stock = yf.Ticker(ticker)
        roster = stock.insider_roster_holders

        if roster is None or roster.empty:
            return {"error": f"No insider roster for {ticker}"}

        records = roster.to_dict(orient='records')

        # Clean up dates and NaN values
        for rec in records:
            for key, value in list(rec.items()):
                new_key = key.lower().replace(' ', '_')
                if new_key != key:
                    rec[new_key] = rec.pop(key)
                    value = rec[new_key]
                if hasattr(value, 'isoformat'):
                    rec[new_key] = value.isoformat()
                elif isinstance(value, float) and value != value:  # NaN
                    rec[new_key] = None

        return {"ticker": ticker, "count": len(records), "insiders": records}
    except Exception as e:
        return {"error": f"Failed to fetch insider roster for {ticker}: {str(e)}"}


# ============================================================================
# BULK/COMPARISON TOOLS (HIGHEST PTC VALUE)
# ============================================================================

@mcp.tool()
def get_multiple_stocks_history(
    tickers: List[str],
    period: str = "1y",
    interval: str = "1d"
) -> dict:
    """
    Get historical data for multiple stocks in a single call.

    VERY HIGH PTC VALUE: Returns N × 252 rows per year for N stocks.
    Ideal for portfolio analysis, correlation studies, and comparative performance.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
        period: Data period - 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: Data interval - 1d, 5d, 1wk, 1mo, 3mo

    Returns:
        dict: {
            "period": str,
            "interval": str,
            "data": {ticker: {"count": int, "history": list[dict]}},
            "successful_tickers": list[str],
            "total_data_points": int,
            "errors": list[str]  # Optional, only if errors occurred
        }
        Use pd.DataFrame(result["data"]["AAPL"]["history"]) to convert to DataFrame.
    """
    result = {"period": period, "interval": interval, "data": {}}
    errors = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)
            if hist.empty:
                errors.append(f"No data for {ticker}")
                continue
            history = _serialize_history(hist)
            result["data"][ticker] = {
                "count": len(history),
                "history": history
            }
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")

    if errors:
        result["errors"] = errors

    result["successful_tickers"] = list(result["data"].keys())
    result["total_data_points"] = sum(
        d.get("count", 0) for d in result["data"].values()
    )

    return result


@mcp.tool()
def compare_financials(
    tickers: List[str],
    statement_type: str = "income",
    quarterly: bool = True
) -> dict:
    """
    Get financial statements for multiple companies for side-by-side comparison.

    VERY HIGH PTC VALUE: Returns N companies × 4 periods × 30+ line items.
    Ideal for peer comparison, sector analysis, and competitive benchmarking.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
        statement_type: Type of statement - "income", "balance", or "cashflow"
        quarterly: If True, returns quarterly data; if False, returns annual

    Returns:
        Dictionary with each ticker's financial statement: {ticker: {data}}
    """
    result = {
        "statement_type": statement_type,
        "quarterly": quarterly,
        "data": {}
    }
    errors = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)

            if statement_type == "income":
                df = stock.quarterly_income_stmt if quarterly else stock.income_stmt
            elif statement_type == "balance":
                df = stock.quarterly_balance_sheet if quarterly else stock.balance_sheet
            elif statement_type == "cashflow":
                df = stock.quarterly_cashflow if quarterly else stock.cashflow
            else:
                errors.append(f"Invalid statement_type: {statement_type}")
                continue

            if df is None or df.empty:
                errors.append(f"No {statement_type} data for {ticker}")
                continue

            result["data"][ticker] = _serialize_dataframe(df)
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")

    if errors:
        result["errors"] = errors

    result["successful_tickers"] = list(result["data"].keys())

    return result


@mcp.tool()
def get_multiple_stocks_dividends(
    tickers: List[str]
) -> dict:
    """
    Get dividend history for multiple stocks in a single call.

    VERY HIGH PTC VALUE: Returns dividend history for N stocks.
    Ideal for portfolio income analysis and dividend comparison.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])

    Returns:
        dict: {
            "data": {ticker: {"dividends": list[dict], "count": int}},
            "successful_tickers": list[str],
            "total_dividends": int,
            "errors": list[str]  # Optional
        }
    """
    result = {"data": {}}
    errors = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            dividends = stock.dividends

            dividend_records = []
            if dividends is not None and not dividends.empty:
                for date, amount in dividends.items():
                    dividend_records.append({
                        "date": date.strftime('%Y-%m-%d'),
                        "amount": round(float(amount), 4)
                    })

            result["data"][ticker] = {
                "dividends": dividend_records,
                "count": len(dividend_records)
            }
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")

    if errors:
        result["errors"] = errors

    result["successful_tickers"] = list(result["data"].keys())
    result["total_dividends"] = sum(d["count"] for d in result["data"].values())

    return result


@mcp.tool()
def get_multiple_stocks_earnings(
    tickers: List[str],
    quarterly: bool = True
) -> dict:
    """
    Get earnings data for multiple stocks in a single call.

    VERY HIGH PTC VALUE: Returns earnings history for N stocks.
    Ideal for earnings season analysis and peer comparison.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
        quarterly: If True, returns quarterly data; if False, returns annual data

    Returns:
        dict: {
            "quarterly": bool,
            "data": {ticker: {"earnings": list[dict], "count": int}},
            "successful_tickers": list[str],
            "errors": list[str]  # Optional
        }
    """
    result = {"quarterly": quarterly, "data": {}}
    errors = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            if quarterly:
                earnings = stock.quarterly_earnings
            else:
                earnings = stock.earnings

            if earnings is None or earnings.empty:
                errors.append(f"No earnings data for {ticker}")
                continue

            earnings = earnings.reset_index()
            records = []
            for _, row in earnings.iterrows():
                record = {}
                for col in earnings.columns:
                    val = row[col]
                    col_name = col.lower().replace(' ', '_')
                    if hasattr(val, 'strftime'):
                        record[col_name] = val.strftime('%Y-%m-%d')
                    elif hasattr(val, 'isoformat'):
                        record[col_name] = val.isoformat()
                    elif isinstance(val, float) and val != val:  # NaN
                        record[col_name] = None
                    else:
                        record[col_name] = val
                records.append(record)

            result["data"][ticker] = {
                "earnings": records,
                "count": len(records)
            }
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")

    if errors:
        result["errors"] = errors

    result["successful_tickers"] = list(result["data"].keys())

    return result


@mcp.tool()
def compare_valuations(
    tickers: List[str]
) -> dict:
    """
    Compare valuation metrics (P/E, P/B, dividend yield, etc.) across multiple stocks.

    VERY HIGH PTC VALUE: Returns valuation multiples for N stocks.
    Ideal for relative valuation analysis, value screening, and peer comparison.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])

    Returns:
        dict: {
            "data": {ticker: {pe_ratio, pb_ratio, dividend_yield, market_cap, ...}},
            "successful_tickers": list[str],
            "errors": list[str]  # Optional
        }
    """
    result = {"data": {}}
    errors = []

    # Key valuation metrics to extract from stock.info
    valuation_keys = [
        "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
        "enterpriseToEbitda", "enterpriseToRevenue", "pegRatio",
        "dividendYield", "payoutRatio", "marketCap", "enterpriseValue",
        "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "fiftyDayAverage",
        "twoHundredDayAverage", "currentPrice"
    ]

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info:
                errors.append(f"No info data for {ticker}")
                continue

            valuations = {}
            for key in valuation_keys:
                val = info.get(key)
                # Convert key to snake_case
                snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                if val is None or (isinstance(val, float) and val != val):  # NaN
                    valuations[snake_key] = None
                else:
                    valuations[snake_key] = val

            result["data"][ticker] = valuations
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")

    if errors:
        result["errors"] = errors

    result["successful_tickers"] = list(result["data"].keys())

    return result


# Run the server
if __name__ == "__main__":
    mcp.run(transport="stdio")
