#!/usr/bin/env python3
"""
Setup script for the LangGraph Store table in PostgreSQL.

The store table is used by SummarizationMiddleware to persist offloaded tool
call IDs across turns.  LangGraph's built-in store.setup() requires autocommit
(for CREATE INDEX CONCURRENTLY), so it fails on shared connection pools.
Run this script once to create the table manually.

Usage:
    uv run python scripts/setup_store_table.py
"""

import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env")

import psycopg


async def setup_store_table():
    """Create the LangGraph store table with autocommit connection."""

    print("Setting up LangGraph Store table...")

    storage_type = os.getenv("DB_TYPE", "memory")
    if storage_type != "postgres":
        print(f"Error: Storage type is '{storage_type}', not 'postgres'")
        print("   Please set DB_TYPE=postgres in .env file")
        return False

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    sslmode = "require" if "supabase.com" in db_host else "disable"

    db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={sslmode}"

    print(f"\n   Database: {db_host}:{db_port}/{db_name} (ssl={sslmode})")

    try:
        # autocommit=True is required for CREATE INDEX CONCURRENTLY
        conn = await psycopg.AsyncConnection.connect(
            db_uri, autocommit=True, prepare_threshold=0
        )
    except Exception as e:
        print(f"\n   Error connecting: {e}")
        return False

    try:
        # Migration 0: store table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS store (
                prefix text NOT NULL,
                key text NOT NULL,
                value jsonb NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (prefix, key)
            )
        """)
        print("   1/4  store table")

        # Migration 1: prefix index (CONCURRENTLY needs autocommit)
        await conn.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS store_prefix_idx
            ON store USING btree (prefix text_pattern_ops)
        """)
        print("   2/4  store_prefix_idx")

        # Migration 2: TTL columns
        await conn.execute("""
            ALTER TABLE store
            ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS ttl_minutes INT
        """)
        print("   3/4  TTL columns")

        # Migration 3: TTL index
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_store_expires_at ON store (expires_at)
            WHERE expires_at IS NOT NULL
        """)
        print("   4/4  idx_store_expires_at")

        # Track migrations so store.setup() doesn't re-run them
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS store_migrations (
                v INTEGER PRIMARY KEY
            )
        """)
        for v in range(4):
            await conn.execute(
                "INSERT INTO store_migrations (v) VALUES (%s) ON CONFLICT DO NOTHING",
                (v,),
            )
        print("   store_migrations tracking updated")

        # Verify
        cur = await conn.execute("SELECT COUNT(*) FROM store")
        row = await cur.fetchone()
        print(f"\n   Done. store table ready ({row[0]} existing rows)")
        return True

    except Exception as e:
        print(f"\n   Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()


if __name__ == "__main__":
    success = asyncio.run(setup_store_table())
    sys.exit(0 if success else 1)
