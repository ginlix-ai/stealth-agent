#!/usr/bin/env python3
"""
Setup script for initializing conversation database tables in PostgreSQL.

This script creates the schema for storing conversation history, threads,
queries, responses, usage tracking, and filesystem state, replacing the legacy
conversations/conversation_threads tables.

Tables created:
- conversation_history: Top-level conversations
- conversation_thread: Workflow execution threads
- conversation_query: User queries with pair_index
- conversation_response: System responses with state snapshots
- conversation_usage: Usage tracking (tokens, infrastructure, credits)
- conversation_filesystems: Filesystem state per conversation
- conversation_files: Files within filesystem (current state only)
- conversation_file_operations: File operation audit trail
- workspaces: Workspace management with Daytona sandbox mapping

Usage:
    uv run python scripts/db/setup_conversation_tables.py
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

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


async def setup_query_response_tables_async():
    """Initialize query-response logging tables in PostgreSQL."""

    print("🔧 Setting up query-response logging tables...")
    print("⚠️  WARNING: This will DROP the legacy conversations and conversation_threads tables!")

    # Get deployment region
    deployment_region = os.getenv("DEPLOYMENT_REGION", "us").lower()
    print(f"\n🌍 Deployment Region: {deployment_region.upper()}")

    # Get database configuration from environment variables based on region
    if deployment_region == "cn":
        # CN environment: Use INFOFLOW_DB_CN_* variables
        print("   Using CN environment database configuration (INFOFLOW_DB_CN_*)")
        db_host = os.getenv("INFOFLOW_DB_CN_HOST", "localhost")
        db_port = os.getenv("INFOFLOW_DB_CN_PORT", "5432")
        db_name = os.getenv("INFOFLOW_DB_CN_NAME")
        db_user = os.getenv("INFOFLOW_DB_CN_USER")
        db_password = os.getenv("INFOFLOW_DB_CN_PASSWORD", "")
    else:
        # US environment (default): Use DB_* variables
        print("   Using US environment database configuration (DB_*)")
        storage_type = os.getenv("DB_TYPE", "memory")

        if storage_type != "postgres":
            print(f"❌ Storage type is '{storage_type}', not 'postgres'")
            print("   Please set DB_TYPE=postgres in .env file")
            return False

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
            print("✅ Connected successfully!")

            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    # Drop legacy tables (no backward compatibility)
                    print("\n🗑️  Dropping legacy tables...")
                    await cur.execute("DROP TABLE IF EXISTS conversation_threads CASCADE;")
                    await cur.execute("DROP TABLE IF EXISTS conversations CASCADE;")
                    print("✅ Legacy tables dropped!")

                    # Create conversation_history table
                    print("\n📝 Creating 'conversation_history' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_history (
                            conversation_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            user_id VARCHAR(255) NOT NULL,
                            title VARCHAR(500),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """)

                    # Create indexes for conversation_history
                    print("   Creating indexes on 'conversation_history'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_history_user_id
                        ON conversation_history(user_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_history_created_at
                        ON conversation_history(created_at DESC);
                    """)
                    print("✅ 'conversation_history' table created!")

                    # Create thread table
                    print("\n📝 Creating 'conversation_thread' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_thread (
                            thread_id VARCHAR(255) PRIMARY KEY,
                            conversation_id VARCHAR(255) NOT NULL REFERENCES conversation_history(conversation_id) ON DELETE CASCADE,
                            msg_type VARCHAR(50),
                            current_status VARCHAR(50) NOT NULL,  -- Status values: in_progress, interrupted, completed, error, cancelled, timeout
                            thread_index INTEGER NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            CONSTRAINT unique_thread_index_per_conversation UNIQUE (conversation_id, thread_index)
                        );
                    """)

                    # Create indexes for thread
                    print("   Creating indexes on 'conversation_thread'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_thread_conversation_id
                        ON conversation_thread(conversation_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_thread_thread_index
                        ON conversation_thread(thread_index);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_thread_created_at
                        ON conversation_thread(created_at DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_thread_current_status
                        ON conversation_thread(current_status);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_thread_msg_type
                        ON conversation_thread(msg_type);
                    """)
                    print("✅ 'conversation_thread' table created!")

                    # Create query table
                    print("\n📝 Creating 'conversation_query' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_query (
                            query_id VARCHAR(255) PRIMARY KEY,
                            thread_id VARCHAR(255) NOT NULL REFERENCES conversation_thread(thread_id) ON DELETE CASCADE,
                            pair_index INTEGER NOT NULL,
                            content TEXT,
                            type VARCHAR(50) NOT NULL,
                            feedback_action TEXT,
                            metadata JSONB DEFAULT '{}'::jsonb,
                            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                            CONSTRAINT unique_pair_index_per_thread_query UNIQUE (thread_id, pair_index)
                        );
                    """)

                    # Create indexes for query
                    print("   Creating indexes on 'conversation_query'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_query_thread_id
                        ON conversation_query(thread_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_query_pair_index
                        ON conversation_query(pair_index);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_query_timestamp
                        ON conversation_query(timestamp DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_query_type
                        ON conversation_query(type);
                    """)
                    print("✅ 'conversation_query' table created!")

                    # Create response table
                    print("\n📝 Creating 'conversation_response' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_response (
                            response_id VARCHAR(255) PRIMARY KEY,
                            thread_id VARCHAR(255) NOT NULL REFERENCES conversation_thread(thread_id) ON DELETE CASCADE,
                            pair_index INTEGER NOT NULL,
                            final_output JSONB,
                            status VARCHAR(50) NOT NULL,
                            interrupt_reason VARCHAR(100),
                            token_usage JSONB,
                            agent_messages JSONB,
                            metadata JSONB DEFAULT '{}'::jsonb,
                            state_snapshot JSONB,
                            warnings TEXT[],
                            errors TEXT[],
                            execution_time FLOAT,
                            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                            streaming_chunks JSONB,
                            CONSTRAINT unique_pair_index_per_thread_response UNIQUE (thread_id, pair_index)
                        );
                    """)

                    # Create indexes for response
                    print("   Creating indexes on 'conversation_response'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_response_thread_id
                        ON conversation_response(thread_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_response_pair_index
                        ON conversation_response(pair_index);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_response_status
                        ON conversation_response(status);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_response_timestamp
                        ON conversation_response(timestamp DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversation_response_streaming_chunks
                        ON conversation_response USING GIN (streaming_chunks);
                    """)
                    print("✅ 'conversation_response' table created!")

                    # Create usage table
                    print("\n📝 Creating 'conversation_usage' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_usage (
                            usage_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            response_id VARCHAR(255) UNIQUE NOT NULL REFERENCES conversation_response(response_id) ON DELETE CASCADE,

                            -- Denormalized fields for fast user-level queries
                            user_id VARCHAR(255) NOT NULL,
                            thread_id VARCHAR(255) NOT NULL REFERENCES conversation_thread(thread_id) ON DELETE CASCADE,
                            conversation_id VARCHAR(255) NOT NULL REFERENCES conversation_history(conversation_id) ON DELETE CASCADE,

                            -- Workflow metadata
                            msg_type VARCHAR(50) NOT NULL DEFAULT 'chat',
                            status VARCHAR(50) NOT NULL,

                            -- Usage data
                            token_usage JSONB,
                            infrastructure_usage JSONB,

                            -- Credit breakdown
                            token_credits DECIMAL(10, 6) NOT NULL DEFAULT 0,
                            infrastructure_credits DECIMAL(10, 6) NOT NULL DEFAULT 0,
                            total_credits DECIMAL(10, 6) NOT NULL DEFAULT 0,

                            -- Timestamps
                            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """)

                    # Create indexes for usage
                    print("   Creating indexes on 'conversation_usage'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_user_id
                        ON conversation_usage(user_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_user_timestamp
                        ON conversation_usage(user_id, timestamp DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_response_id
                        ON conversation_usage(response_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_thread_id
                        ON conversation_usage(thread_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_conversation_id
                        ON conversation_usage(conversation_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                        ON conversation_usage(timestamp DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_user_credits
                        ON conversation_usage(user_id, timestamp DESC, total_credits);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_msg_type
                        ON conversation_usage(msg_type);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_status
                        ON conversation_usage(status);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_user_msg_type
                        ON conversation_usage(user_id, msg_type, timestamp DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_user_status
                        ON conversation_usage(user_id, status, timestamp DESC);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_token_usage_gin
                        ON conversation_usage USING GIN (token_usage);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_infrastructure_usage_gin
                        ON conversation_usage USING GIN (infrastructure_usage);
                    """)
                    print("✅ 'conversation_usage' table created!")

                    # Create filesystem tables
                    print("\n📝 Creating 'conversation_filesystems' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_filesystems (
                            filesystem_id VARCHAR(255) PRIMARY KEY,
                            conversation_id VARCHAR(255) UNIQUE NOT NULL REFERENCES conversation_history(conversation_id) ON DELETE CASCADE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """)

                    print("   Creating indexes on 'conversation_filesystems'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_filesystems_conversation
                        ON conversation_filesystems(conversation_id);
                    """)
                    print("✅ 'conversation_filesystems' table created!")

                    print("\n📝 Creating 'conversation_files' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_files (
                            file_id VARCHAR(255) PRIMARY KEY,
                            filesystem_id VARCHAR(255) NOT NULL REFERENCES conversation_filesystems(filesystem_id) ON DELETE CASCADE,
                            file_path TEXT NOT NULL,
                            content TEXT,
                            line_count INTEGER,
                            created_in_thread_id VARCHAR(255),
                            created_in_pair_index INTEGER,
                            updated_in_thread_id VARCHAR(255),
                            updated_in_pair_index INTEGER,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            CONSTRAINT unique_file_path_per_filesystem UNIQUE(filesystem_id, file_path)
                        );
                    """)

                    print("   Creating indexes on 'conversation_files'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_files_filesystem
                        ON conversation_files(filesystem_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_files_path
                        ON conversation_files(filesystem_id, file_path);
                    """)
                    print("✅ 'conversation_files' table created!")

                    print("\n📝 Creating 'conversation_file_operations' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_file_operations (
                            operation_id VARCHAR(255) PRIMARY KEY,
                            file_id VARCHAR(255) NOT NULL REFERENCES conversation_files(file_id) ON DELETE CASCADE,
                            operation VARCHAR(50) NOT NULL,
                            thread_id VARCHAR(255) NOT NULL,
                            pair_index INTEGER NOT NULL,
                            agent VARCHAR(100),
                            tool_call_id VARCHAR(255),
                            old_string TEXT,
                            new_string TEXT,
                            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            operation_index INTEGER NOT NULL
                        );
                    """)

                    print("   Creating indexes on 'conversation_file_operations'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_operations_file
                        ON conversation_file_operations(file_id, timestamp);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_operations_file_index
                        ON conversation_file_operations(file_id, operation_index);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_operations_thread
                        ON conversation_file_operations(thread_id, pair_index);
                    """)
                    print("✅ 'conversation_file_operations' table created!")

                    # Create workspaces table
                    print("\n📝 Creating 'workspaces' table...")
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS workspaces (
                            workspace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            user_id VARCHAR(255) NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,

                            -- Sandbox reference (Daytona)
                            sandbox_id VARCHAR(255),

                            -- Lifecycle state
                            -- Values: creating, running, stopping, stopped, error, deleted
                            status VARCHAR(50) NOT NULL DEFAULT 'creating',

                            -- Timestamps
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            last_activity_at TIMESTAMPTZ,
                            stopped_at TIMESTAMPTZ,

                            -- Configuration (flexible)
                            config JSONB DEFAULT '{}'::jsonb
                        );
                    """)

                    print("   Creating indexes on 'workspaces'...")
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_workspaces_user_id
                        ON workspaces(user_id);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_workspaces_status
                        ON workspaces(status);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_workspaces_user_status
                        ON workspaces(user_id, status);
                    """)
                    await cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_workspaces_updated_at
                        ON workspaces(updated_at DESC);
                    """)
                    print("✅ 'workspaces' table created!")

                    # Verify tables exist
                    print("\n🔍 Verifying tables...")
                    await cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name IN (
                            'conversation_history',
                            'conversation_thread',
                            'conversation_query',
                            'conversation_response',
                            'conversation_usage',
                            'conversation_filesystems',
                            'conversation_files',
                            'conversation_file_operations',
                            'workspaces'
                        )
                        ORDER BY table_name;
                    """)

                    tables = await cur.fetchall()
                    print(f"   Found {len(tables)} tables:")
                    for table in tables:
                        print(f"     ✓ {table['table_name']}")

            print("\n🎉 Setup complete! Conversation database tables are ready.")
            print("\n📋 Schema Summary:")
            print("   • conversation_history: Top-level conversations")
            print("   • conversation_thread: Workflow execution threads")
            print("   • conversation_query: User queries with pair_index")
            print("   • conversation_response: System responses with state snapshots")
            print("   • conversation_usage: Usage tracking (tokens, infrastructure, credits)")
            print("   • conversation_filesystems: Filesystem state per conversation")
            print("   • conversation_files: Files within filesystem")
            print("   • conversation_file_operations: File operation audit trail")
            print("   • workspaces: Workspace management with Daytona sandbox mapping")
            print("\n⚠️  Note: Legacy tables (conversations, conversation_threads) have been dropped.")
            return True

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        print("\nPlease check:")
        print("  1. Database credentials in .env file are correct")
        print("  2. Database server is accessible (SSH tunnel if needed)")
        print("  3. User has permission to create/drop tables")
        import traceback
        traceback.print_exc()
        return False


def setup_query_response_tables():
    """Synchronous wrapper for async setup function."""
    return asyncio.run(setup_query_response_tables_async())


if __name__ == "__main__":
    success = setup_query_response_tables()
    sys.exit(0 if success else 1)
