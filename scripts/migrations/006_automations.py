#!/usr/bin/env python3
"""
Migration 006: Create automations and automation_executions tables.

Adds the foundation for time-based (cron/once) automation triggers
that invoke the agent on a schedule.

Idempotent -- safe to re-run.

Usage:
    uv run python scripts/migrations/006_automations.py
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


async def table_exists(cur, table: str) -> bool:
    await cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """, (table,))
    result = await cur.fetchone()
    return result['exists']


async def main():
    print("Migration 006: Create automations tables")
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
                    # ---------------------------------------------------------
                    # 1. automations table
                    # ---------------------------------------------------------
                    if await table_exists(cur, 'automations'):
                        print("   automations table already exists, skipping.")
                    else:
                        await cur.execute("""
                            CREATE TABLE IF NOT EXISTS automations (
                                automation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                user_id             VARCHAR(255) NOT NULL
                                                        REFERENCES users(user_id) ON DELETE CASCADE,

                                -- Display
                                name                VARCHAR(255) NOT NULL,
                                description         TEXT,

                                -- Trigger
                                trigger_type        VARCHAR(20) NOT NULL
                                                        CHECK (trigger_type IN ('cron', 'once')),
                                cron_expression     VARCHAR(100),
                                timezone            VARCHAR(100) NOT NULL DEFAULT 'UTC',
                                trigger_config      JSONB DEFAULT '{}'::jsonb,

                                -- Timing
                                next_run_at         TIMESTAMPTZ,
                                last_run_at         TIMESTAMPTZ,

                                -- Agent config
                                agent_mode          VARCHAR(20) NOT NULL DEFAULT 'flash'
                                                        CHECK (agent_mode IN ('ptc', 'flash')),
                                instruction         TEXT NOT NULL,
                                workspace_id        UUID
                                                        REFERENCES workspaces(workspace_id) ON DELETE SET NULL,
                                llm_model           VARCHAR(100),
                                additional_context  JSONB,

                                -- Thread strategy
                                thread_strategy     VARCHAR(20) NOT NULL DEFAULT 'new'
                                                        CHECK (thread_strategy IN ('new', 'continue')),
                                conversation_thread_id UUID,

                                -- Lifecycle
                                status              VARCHAR(20) NOT NULL DEFAULT 'active'
                                                        CHECK (status IN ('active', 'paused', 'completed', 'disabled')),
                                max_failures        INT NOT NULL DEFAULT 3,
                                failure_count       INT NOT NULL DEFAULT 0,

                                -- Future extensibility
                                delivery_config     JSONB DEFAULT '{}'::jsonb,
                                metadata            JSONB DEFAULT '{}'::jsonb,

                                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            );
                        """)
                        print("   Created automations table")

                        # Polling index
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_automations_next_run
                                ON automations(next_run_at ASC)
                                WHERE status = 'active' AND next_run_at IS NOT NULL;
                        """)
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_automations_user_id
                                ON automations(user_id);
                        """)
                        print("   Created automations indexes")

                        # updated_at trigger
                        await cur.execute("""
                            DROP TRIGGER IF EXISTS trg_automations_updated_at ON automations;
                        """)
                        await cur.execute("""
                            CREATE TRIGGER trg_automations_updated_at
                                BEFORE UPDATE ON automations
                                FOR EACH ROW
                                EXECUTE FUNCTION update_updated_at_column();
                        """)
                        print("   Created automations updated_at trigger")

                    # ---------------------------------------------------------
                    # 2. automation_executions table
                    # ---------------------------------------------------------
                    if await table_exists(cur, 'automation_executions'):
                        print("   automation_executions table already exists, skipping.")
                    else:
                        await cur.execute("""
                            CREATE TABLE IF NOT EXISTS automation_executions (
                                automation_execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                                automation_id       UUID NOT NULL
                                                        REFERENCES automations(automation_id) ON DELETE CASCADE,

                                status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                                                        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'timeout')),

                                conversation_thread_id UUID,
                                scheduled_at        TIMESTAMPTZ NOT NULL,
                                started_at          TIMESTAMPTZ,
                                completed_at        TIMESTAMPTZ,
                                error_message       TEXT,
                                server_id           VARCHAR(100),

                                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            );
                        """)
                        print("   Created automation_executions table")

                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_automation_executions_automation_id
                                ON automation_executions(automation_id);
                        """)
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_automation_executions_status
                                ON automation_executions(status);
                        """)
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_automation_executions_created_at
                                ON automation_executions(created_at DESC);
                        """)
                        print("   Created automation_executions indexes")

            print("\nMigration 006 complete.")
            return True

    except Exception as e:
        print(f"\nMigration error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
