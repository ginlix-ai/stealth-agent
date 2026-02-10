"""
LangGraph Checkpointer Utilities

Provides PostgreSQL, SQLite, and in-memory checkpointers for LangGraph workflows.
This module is standalone and does not depend on deep_research.
"""

import asyncio
import logging
import os
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

# Module-level connection pool cache to reuse connections across graph compilations
_postgres_pool_cache: dict[str, AsyncConnectionPool] = {}


def _on_reconnect_failed(pool):
    """Callback when pool fails to reconnect after reconnect_timeout."""
    logger.critical(
        f"[Checkpointer] Connection pool failed to reconnect after "
        f"reconnect_timeout. Pool stats: {pool.get_stats()}"
    )


async def _configure_postgres_connection(conn) -> None:
    """
    Configure PostgreSQL connection for Supabase compatibility.

    Disables prepared statements which cause issues with Supabase poolers
    (both session and transaction modes).

    This is critical - without this, you get:
    - "prepared statement already exists" errors
    - Connection failures with poolers
    """
    conn.prepare_threshold = 0
    logger.debug("Configured checkpoint connection with prepare_threshold=0")


def get_checkpointer(memory_type: str = "memory", **kwargs) -> Optional[Any]:
    """
    Get checkpointer based on storage type.

    Args:
        memory_type: Storage type ("memory", "postgres")
        **kwargs: Database connection parameters:
            - db_host: Database host
            - db_port: Database port
            - db_name: Database name
            - db_user: Database user
            - db_password: Database password

    Returns:
        Checkpointer instance (MemorySaver or AsyncPostgresSaver)

    Raises:
        ValueError: If unsupported storage type is provided
    """
    if memory_type == "memory":
        logger.info("Using in-memory checkpointer")
        return MemorySaver()

    elif memory_type == "postgres":
        # Get database connection info from kwargs or environment variables
        db_host = kwargs.get("db_host") or os.getenv("MEMORY_DB_HOST", "localhost")
        db_port = kwargs.get("db_port") or os.getenv("MEMORY_DB_PORT", "5432")
        db_name = kwargs.get("db_name") or os.getenv("MEMORY_DB_NAME", "postgres")
        db_user = kwargs.get("db_user") or os.getenv("MEMORY_DB_USER", "postgres")
        db_password = kwargs.get("db_password") or os.getenv("MEMORY_DB_PASSWORD", "postgres")

        # Auto-detect SSL mode for Supabase
        sslmode = "require" if "supabase.com" in db_host else "disable"
        db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={sslmode}"

        # Cache connection pools by URI to avoid creating new pools on every graph instantiation
        if db_uri not in _postgres_pool_cache:
            logger.info(f"Creating PostgreSQL connection pool for checkpointer: {db_host}:{db_port}/{db_name}")
            _postgres_pool_cache[db_uri] = AsyncConnectionPool(
                conninfo=db_uri,
                min_size=1,
                max_size=10,
                configure=_configure_postgres_connection,
                check=AsyncConnectionPool.check_connection,
                open=False,  # Defer opening until async context is available
                reconnect_failed=_on_reconnect_failed,
                kwargs={
                    "connect_timeout": 10,
                    "keepalives": 1,
                    "keepalives_idle": 60,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                },
            )

        pool = _postgres_pool_cache[db_uri]
        return AsyncPostgresSaver(pool)

    else:
        raise ValueError(f"Unsupported storage type: {memory_type}")


async def open_checkpointer_pool(checkpointer: Any) -> bool:
    """
    Open the connection pool for a PostgreSQL checkpointer.

    Must be called from an async context before using the checkpointer.

    Args:
        checkpointer: Checkpointer instance (from get_checkpointer)

    Returns:
        True if pool was opened, False if not applicable (e.g., memory checkpointer)
    """
    if checkpointer and hasattr(checkpointer, "conn"):
        pool = checkpointer.conn
        if hasattr(pool, "open") and hasattr(pool, "closed"):
            if pool.closed:
                await pool.open()
                logger.info("Checkpointer PostgreSQL pool opened")
                return True
            else:
                logger.debug("Checkpointer PostgreSQL pool already open")
    return False


async def close_checkpointer_pool(checkpointer: Any) -> bool:
    """
    Close the connection pool for a PostgreSQL checkpointer.

    Should be called during application shutdown.

    Args:
        checkpointer: Checkpointer instance

    Returns:
        True if pool was closed, False if not applicable
    """
    if checkpointer and hasattr(checkpointer, "conn"):
        pool = checkpointer.conn
        if hasattr(pool, "close") and hasattr(pool, "closed"):
            if not pool.closed:
                await pool.close()
                logger.info("Checkpointer PostgreSQL pool closed")
                return True
            else:
                logger.debug("Checkpointer PostgreSQL pool already closed")
    return False


async def get_checkpointer_health(checkpointer: Any) -> dict:
    """
    Get checkpointer connection pool health stats.

    Returns pool statistics and runs a quick SELECT 1 connectivity test.

    Args:
        checkpointer: Checkpointer instance (from get_checkpointer)

    Returns:
        Dict with status, pool stats, and connectivity info
    """
    if not checkpointer or not hasattr(checkpointer, "conn"):
        return {"status": "not_configured"}

    pool = checkpointer.conn

    # Get pool statistics
    if not hasattr(pool, "get_stats"):
        return {"status": "not_configured", "reason": "not_a_pool"}

    stats = pool.get_stats()

    # Run a quick connection test
    healthy = False
    error_msg = None
    try:
        async with asyncio.timeout(5.0):
            async with pool.connection() as conn:
                await conn.execute("SELECT 1")
                healthy = True
    except TimeoutError:
        error_msg = "connection test timed out (5s)"
    except Exception as e:
        error_msg = str(e)

    result = {
        "status": "healthy" if healthy else "unhealthy",
        "pool_size": stats.get("pool_size", 0),
        "pool_available": stats.get("pool_available", 0),
        "requests_waiting": stats.get("requests_waiting", 0),
        "pool_min": stats.get("pool_min", 0),
        "pool_max": stats.get("pool_max", 0),
    }
    if error_msg:
        result["error"] = error_msg

    return result
