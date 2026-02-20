#!/usr/bin/env python3
"""
Migration 005: Add auth_provider column to users table.

Records which authentication channel (google, github, email, etc.) was used
to create the account.  Extracted from the Supabase JWT's
``app_metadata.provider`` field during auth sync.

Idempotent -- safe to re-run.

Usage:
    uv run python scripts/migrations/005_add_auth_provider.py
"""

import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / ".env")

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


async def column_exists(cur, table: str, col: str) -> bool:
    await cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        )
    """, (table, col))
    result = await cur.fetchone()
    return result['exists']


async def main():
    print("Migration 005: Add auth_provider column")
    print("=" * 50)

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    sslmode = "require" if "supabase.com" in db_host else "disable"
    db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={sslmode}"

    print(f"Database: {db_host}:{db_port}/{db_name}")

    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    }

    try:
        async with AsyncConnectionPool(
            conninfo=db_uri,
            min_size=1,
            max_size=1,
            kwargs=connection_kwargs,
        ) as pool:
            await pool.wait()
            print("Connected to database\n")

            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    if await column_exists(cur, 'users', 'auth_provider'):
                        print("   users.auth_provider already exists, nothing to do.")
                    else:
                        await cur.execute(
                            "ALTER TABLE users ADD COLUMN auth_provider VARCHAR(50)"
                        )
                        print("   Added users.auth_provider VARCHAR(50)")

            print("\nMigration 005 complete.")
            return True

    except Exception as e:
        print(f"\nMigration error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
