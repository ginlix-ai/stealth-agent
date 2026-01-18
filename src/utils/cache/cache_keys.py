"""
Cache key generation utilities.

Provides consistent, deterministic key generation for caching
with support for pattern matching and bulk invalidation.
"""

import hashlib
from typing import Any, Dict, Optional
from urllib.parse import urlencode


class CacheKeyBuilder:
    """
    Builder for generating consistent cache keys.

    Features:
    - Namespace support
    - Deterministic key generation (sorted params)
    - URL-safe encoding
    - Pattern matching support
    """

    def __init__(self, namespace: str):
        """
        Initialize key builder.

        Args:
            namespace: Key namespace prefix
        """
        self.namespace = namespace

    @staticmethod
    def _normalize_params(params: Dict[str, Any]) -> str:
        """
        Normalize query parameters to consistent format.

        - Sorts keys alphabetically
        - Handles None values
        - Converts to URL-encoded string

        Args:
            params: Query parameters

        Returns:
            Normalized parameter string
        """
        # Filter out None values
        filtered = {k: v for k, v in params.items() if v is not None}

        # Sort keys for consistency
        sorted_params = sorted(filtered.items())

        # URL encode
        return urlencode(sorted_params)

    @staticmethod
    def _hash_params(params_str: str) -> str:
        """
        Generate short hash of parameters.

        Useful for very long parameter strings to keep keys manageable.

        Args:
            params_str: Parameter string

        Returns:
            MD5 hash (first 16 characters)
        """
        return hashlib.md5(params_str.encode()).hexdigest()[:16]

    def build(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        use_hash: bool = False,
    ) -> str:
        """
        Build cache key.

        Args:
            resource: Resource identifier (e.g., "list", "detail")
            params: Query parameters
            use_hash: Whether to hash params for shorter keys

        Returns:
            Cache key string

        Example:
            builder = CacheKeyBuilder("myapp:data")
            key = builder.build("list", {"limit": 20, "filter": "active"})
            # Returns: "myapp:data:list:filter=active&limit=20"
        """
        parts = [self.namespace, resource]

        if params:
            params_str = self._normalize_params(params)

            if use_hash:
                params_str = self._hash_params(params_str)

            parts.append(params_str)

        return ":".join(parts)

    def pattern(self, resource: Optional[str] = None, prefix: str = "*") -> str:
        """
        Build pattern for matching multiple keys.

        Args:
            resource: Resource identifier (None for all resources)
            prefix: Wildcard prefix for params

        Returns:
            Key pattern for Redis SCAN

        Example:
            builder = CacheKeyBuilder("myapp:data")
            pattern = builder.pattern("list")
            # Returns: "myapp:data:list:*"
        """
        if resource:
            return f"{self.namespace}:{resource}:{prefix}"
        return f"{self.namespace}:{prefix}"
