#!/usr/bin/env python3
"""
Setup script for initializing LangGraph checkpoint tables in PostgreSQL/Supabase.

This script creates the necessary checkpoint tables for LangGraph state persistence.
Run this once before using the deep_research workflow with PostgreSQL storage.

Usage:
    uv run python scripts/db/setup_checkpoint_tables.py
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

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


async def setup_checkpoint_tables_async():
    """Initialize checkpoint tables in the configured PostgreSQL database."""

    print("🔧 Setting up LangGraph checkpoint tables...")

    # Get database configuration from environment variables
    storage_type = os.getenv("DB_TYPE", "memory")

    if storage_type != "postgres":
        print(f"❌ Storage type is '{storage_type}', not 'postgres'")
        print("   Please set DB_TYPE=postgres in .env file")
        return False

    # Build connection string from environment variables
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    # Determine SSL mode based on host
    sslmode = "require" if "supabase.com" in db_host else "disable"

    db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={sslmode}"

    print(f"\n📊 Database Configuration:")
    print(f"   Host: {db_host}")
    print(f"   Port: {db_port}")
    print(f"   Database: {db_name}")
    print(f"   User: {db_user}")
    print(f"   SSL Mode: {sslmode}")

    try:
        print("\n🔌 Connecting to database...")

        # Connection kwargs with prepare_threshold=0 for Supabase transaction pooler
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,  # Disable prepared statements for transaction pooler
            "row_factory": dict_row
        }

        # Create async connection pool
        async with AsyncConnectionPool(
            conninfo=db_uri,
            min_size=1,
            max_size=1,  # Only need 1 connection for setup
            kwargs=connection_kwargs
        ) as pool:
            # Wait for pool to be ready
            await pool.wait()

            # Create checkpointer with pool
            checkpointer = AsyncPostgresSaver(pool)
            print("✅ Connected successfully!")

            print("\n📝 Creating checkpoint tables...")
            await checkpointer.setup()

            print("✅ Checkpoint tables created successfully!")
            print("\n🎉 Setup complete! You can now use PostgreSQL for checkpoint storage.")

        return True

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        print("\nPlease check:")
        print("  1. Database credentials in .env file are correct")
        print("  2. Database server is accessible (SSH tunnel if needed)")
        print("  3. User has permission to create tables")
        return False


def setup_checkpoint_tables():
    """Synchronous wrapper for async setup function."""
    return asyncio.run(setup_checkpoint_tables_async())


if __name__ == "__main__":
    success = setup_checkpoint_tables()
    sys.exit(0 if success else 1)
