"""
Daily stock data caching service with SWR (Stale-While-Revalidate) pattern.

Provides cached access to FMP daily EOD (end-of-day) historical price data.
Modeled after IntradayCacheService but simplified for daily granularity.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.utils.cache.redis_cache import get_cache_client
from src.config.settings import get_nested_config
from src.data_client.fmp.fmp_client import FMPClient

logger = logging.getLogger(__name__)


class DailyCacheKeyBuilder:
    """Build cache keys for daily stock data."""

    PREFIX = "fmp:daily:stock"

    @classmethod
    def stock_key(cls, symbol: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        key = f"{cls.PREFIX}:symbol={symbol.upper()}"
        if from_date:
            key += f":from={from_date}"
        if to_date:
            key += f":to={to_date}"
        return key


@dataclass
class DailyFetchResult:
    """Result of a daily data fetch operation."""
    symbol: str
    data: List[Dict[str, Any]]
    cached: bool
    ttl_remaining: Optional[int]
    background_refresh_triggered: bool
    error: Optional[str] = None


class DailyCacheService:
    """
    Singleton service for cached daily EOD stock data.

    Uses FMPClient.get_stock_price() which returns ~500 days of daily OHLCV by default.
    """

    _instance: Optional["DailyCacheService"] = None
    _refresh_locks: Dict[str, asyncio.Lock]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._refresh_locks = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> "DailyCacheService":
        return cls()

    def _get_ttl(self) -> int:
        return get_nested_config("redis.ttl.daily_stock", 3600)

    def _get_soft_ttl_ratio(self) -> float:
        return get_nested_config("redis.swr.soft_ttl_ratio", 0.5)

    def _get_refresh_lock(self, cache_key: str) -> asyncio.Lock:
        if cache_key not in self._refresh_locks:
            self._refresh_locks[cache_key] = asyncio.Lock()
        return self._refresh_locks[cache_key]

    async def _fetch_from_fmp(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        async with FMPClient() as client:
            data = await client.get_stock_price(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
            )
            return data if data else []

    async def _background_refresh(
        self,
        cache_key: str,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> None:
        lock = self._get_refresh_lock(cache_key)

        if lock.locked():
            logger.debug(f"Background refresh already in progress for {cache_key}")
            return

        async with lock:
            try:
                logger.debug(f"Starting background refresh for {cache_key}")
                data = await self._fetch_from_fmp(symbol, from_date, to_date)
                cache = get_cache_client()
                ttl = self._get_ttl()
                await cache.set(cache_key, data, ttl=ttl)
                logger.debug(f"Background refresh completed for {cache_key}, {len(data)} points")
            except Exception as e:
                logger.warning(f"Background refresh failed for {cache_key}: {e}")

    async def get_stock_daily(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> DailyFetchResult:
        """
        Get daily EOD stock data with SWR caching.

        Args:
            symbol: Stock ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            DailyFetchResult with data and cache metadata
        """
        normalized_symbol = symbol.upper()
        cache_key = DailyCacheKeyBuilder.stock_key(normalized_symbol, from_date, to_date)

        cache = get_cache_client()
        ttl = self._get_ttl()
        soft_ratio = self._get_soft_ttl_ratio()

        cached_data, needs_refresh = await cache.get_with_swr(
            key=cache_key,
            original_ttl=ttl,
            soft_ttl_ratio=soft_ratio,
        )

        background_refresh_triggered = False

        if cached_data is not None:
            ttl_remaining = await cache.ttl(cache_key)
            ttl_remaining = max(0, ttl_remaining) if ttl_remaining > 0 else None

            if needs_refresh:
                background_refresh_triggered = True
                asyncio.create_task(
                    self._background_refresh(cache_key, normalized_symbol, from_date, to_date)
                )

            return DailyFetchResult(
                symbol=normalized_symbol,
                data=cached_data,
                cached=True,
                ttl_remaining=ttl_remaining,
                background_refresh_triggered=background_refresh_triggered,
            )

        # Cache miss - fetch from API
        try:
            data = await self._fetch_from_fmp(normalized_symbol, from_date, to_date)
            await cache.set(cache_key, data, ttl=ttl)

            return DailyFetchResult(
                symbol=normalized_symbol,
                data=data,
                cached=False,
                ttl_remaining=ttl,
                background_refresh_triggered=False,
            )
        except Exception as e:
            logger.error(f"Failed to fetch daily data for {symbol}: {e}")
            return DailyFetchResult(
                symbol=normalized_symbol,
                data=[],
                cached=False,
                ttl_remaining=None,
                background_refresh_triggered=False,
                error=str(e),
            )
