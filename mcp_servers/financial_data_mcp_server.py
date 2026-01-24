#!/usr/bin/env python3
"""Financial Data MCP Server.

This server provides programmatic access to normalized OHLCV time series via MCP.

Design goals:
- Small, stable tool surface (high PTC value)
- Normalized JSON output (schema stable across providers)
- Can run in sandbox (stdio) for OSS/dev
- Can be deployed externally (http/sse) for production

Tools:
- get_stock_data: stock OHLCV
- get_asset_data: stock/commodity/crypto/forex OHLCV
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("FinancialDataMCP")


_INTRADAY_INTERVALS_STOCK = {"1min", "5min", "15min", "30min", "1hour", "4hour"}
_INTRADAY_INTERVALS_ASSET = {"1min", "5min", "1hour"}
_DAILY_INTERVALS = {"daily", "1day"}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_date(value: Any) -> str:
    """Return an ISO string usable for sorting and display."""

    if value is None:
        return ""

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    text = str(value)
    # FMP sometimes returns "YYYY-MM-DD" or full ISO datetime.
    return text


def _normalize_ohlcv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for row in rows:
        normalized_row = {
            "date": _normalize_date(row.get("date")),
            "open": _as_float(row.get("open")),
            "high": _as_float(row.get("high")),
            "low": _as_float(row.get("low")),
            "close": _as_float(row.get("close")),
            "volume": _as_float(row.get("volume")),
        }
        normalized.append(normalized_row)

    # Descending (newest first). ISO strings are sortable lexicographically.
    normalized.sort(key=lambda r: r.get("date") or "", reverse=True)
    return normalized


def _default_dates_for_intraday(from_date: str | None, to_date: str | None) -> tuple[str, str]:
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=7)
    return (
        from_date or start_dt.strftime("%Y-%m-%d"),
        to_date or end_dt.strftime("%Y-%m-%d"),
    )


def _load_fmp_client():
    # Imported lazily so this server can start without FMP_API_KEY.
    from src.data_client.fmp import FMPClient  # local sandbox upload or repo import

    return FMPClient()


@mcp.tool()
async def get_stock_data(
    symbol: str,
    interval: str = "1day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Get normalized OHLCV for a stock symbol.

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT, 600519.SS, 0700.HK)
        interval: "1day"/"daily" or intraday: 1min/5min/15min/30min/1hour/4hour
        start_date: YYYY-MM-DD (optional)
        end_date: YYYY-MM-DD (optional)

    Returns:
        dict: {
          "symbol": str,
          "interval": str,
          "count": int,
          "rows": list[dict],
          "source": "fmp"
        }
        rows are normalized: date/open/high/low/close/volume (descending by date).
    """

    interval_lower = interval.lower()

    try:
        client = _load_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}"}

    try:
        async with client:
            if interval_lower in _DAILY_INTERVALS:
                rows = await client.get_stock_price(symbol, from_date=start_date, to_date=end_date)
            else:
                if interval_lower not in _INTRADAY_INTERVALS_STOCK:
                    return {
                        "error": "Unsupported interval for stock",
                        "supported": sorted(_DAILY_INTERVALS | _INTRADAY_INTERVALS_STOCK),
                    }

                intraday_start, intraday_end = _default_dates_for_intraday(start_date, end_date)
                rows = await client.get_intraday_chart(
                    symbol,
                    interval_lower,
                    from_date=intraday_start,
                    to_date=intraday_end,
                )
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

    normalized = _normalize_ohlcv_rows(rows or [])
    return {
        "symbol": symbol,
        "interval": interval_lower,
        "count": len(normalized),
        "rows": normalized,
        "source": "fmp",
    }


@mcp.tool()
async def get_asset_data(
    symbol: str,
    asset_type: str,
    interval: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """Get normalized OHLCV for stock/commodity/crypto/forex.

    Args:
        symbol: Asset symbol (e.g., GCUSD, BTCUSD, EURUSD, AAPL)
        asset_type: one of stock/commodity/crypto/forex
        interval: daily/1day or intraday
          - stock: 1min/5min/15min/30min/1hour/4hour
          - commodity/crypto/forex: 1min/5min/1hour
        from_date: YYYY-MM-DD (optional)
        to_date: YYYY-MM-DD (optional)

    Returns:
        dict with symbol, asset_type, interval, count, rows (descending), source.
    """

    at = asset_type.lower().strip()
    interval_lower = interval.lower()

    if at not in {"stock", "commodity", "crypto", "forex"}:
        return {"error": "Invalid asset_type", "supported": ["stock", "commodity", "crypto", "forex"]}

    try:
        client = _load_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}"}

    try:
        async with client:
            if at == "stock":
                if interval_lower in _DAILY_INTERVALS:
                    rows = await client.get_stock_price(symbol, from_date=from_date, to_date=to_date)
                else:
                    if interval_lower not in _INTRADAY_INTERVALS_STOCK:
                        return {
                            "error": "Unsupported interval for stock",
                            "supported": sorted(_DAILY_INTERVALS | _INTRADAY_INTERVALS_STOCK),
                        }

                    intraday_start, intraday_end = _default_dates_for_intraday(from_date, to_date)
                    rows = await client.get_intraday_chart(
                        symbol,
                        interval_lower,
                        from_date=intraday_start,
                        to_date=intraday_end,
                    )

            else:
                if interval_lower in _DAILY_INTERVALS:
                    if at == "commodity":
                        rows = await client.get_commodity_price(symbol, from_date=from_date, to_date=to_date)
                    elif at == "crypto":
                        rows = await client.get_crypto_price(symbol, from_date=from_date, to_date=to_date)
                    else:
                        rows = await client.get_forex_price(symbol, from_date=from_date, to_date=to_date)

                else:
                    if interval_lower not in _INTRADAY_INTERVALS_ASSET:
                        return {
                            "error": "Unsupported interval for commodity/crypto/forex",
                            "supported": sorted(_DAILY_INTERVALS | _INTRADAY_INTERVALS_ASSET),
                        }

                    intraday_start, intraday_end = _default_dates_for_intraday(from_date, to_date)
                    if at == "commodity":
                        rows = await client.get_commodity_intraday_chart(
                            symbol,
                            interval_lower,
                            from_date=intraday_start,
                            to_date=intraday_end,
                        )
                    elif at == "crypto":
                        rows = await client.get_crypto_intraday_chart(
                            symbol,
                            interval_lower,
                            from_date=intraday_start,
                            to_date=intraday_end,
                        )
                    else:
                        rows = await client.get_forex_intraday_chart(
                            symbol,
                            interval_lower,
                            from_date=intraday_start,
                            to_date=intraday_end,
                        )

    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

    normalized = _normalize_ohlcv_rows(rows or [])
    return {
        "symbol": symbol,
        "asset_type": at,
        "interval": interval_lower,
        "count": len(normalized),
        "rows": normalized,
        "source": "fmp",
    }


if __name__ == "__main__":
    mcp.run()
