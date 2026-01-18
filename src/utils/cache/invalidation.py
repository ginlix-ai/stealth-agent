"""
Cache invalidation utilities.

Provides basic cache invalidation functionality including:
- Pattern-based cache deletion
- Bulk cache clearing
"""

import logging
from typing import Dict, List, Optional

from src.utils.cache.redis_cache import get_cache_client

logger = logging.getLogger(__name__)


class CacheInvalidator:
    """
    Cache invalidation manager.

    Features:
    - Pattern-based bulk deletion
    - Async operation
    - Error handling and logging
    """

    def __init__(self):
        """Initialize cache invalidator."""
        self.cache = get_cache_client()

    async def invalidate_patterns(self, patterns: List[str]) -> Dict[str, int]:
        """
        Invalidate multiple cache key patterns.

        Args:
            patterns: List of cache key patterns to delete

        Returns:
            Dict mapping pattern to number of keys deleted
        """
        if not self.cache.enabled:
            logger.debug("Cache disabled, skipping invalidation")
            return {}

        results = {}

        for pattern in patterns:
            try:
                deleted_count = await self.cache.delete_pattern(pattern)
                results[pattern] = deleted_count

                if deleted_count > 0:
                    logger.debug(f"Invalidated {deleted_count} keys matching: {pattern}")

            except Exception as e:
                logger.error(f"Failed to invalidate pattern {pattern}: {e}")
                results[pattern] = 0

        return results

    async def invalidate_all(self) -> bool:
        """
        Clear all caches.

        WARNING: This is a nuclear option - use sparingly.

        Returns:
            True if successful, False otherwise
        """
        logger.warning("Clearing ALL caches (nuclear option)")

        # Delete all keys with any common prefix
        patterns = ["*"]

        results = await self.invalidate_patterns(patterns)
        total_deleted = sum(results.values())

        logger.warning(f"All caches cleared: {total_deleted} keys deleted")
        return total_deleted >= 0


# Global invalidator instance
_invalidator: Optional[CacheInvalidator] = None


def get_cache_invalidator() -> CacheInvalidator:
    """
    Get global cache invalidator instance.

    Returns:
        CacheInvalidator instance
    """
    global _invalidator

    if _invalidator is None:
        _invalidator = CacheInvalidator()

    return _invalidator
