-- Migration 008: Add thread sharing support
-- Adds columns for public chat sharing with configurable permissions

ALTER TABLE conversation_threads
  ADD COLUMN IF NOT EXISTS share_token VARCHAR(32) UNIQUE,
  ADD COLUMN IF NOT EXISTS is_shared BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS share_permissions JSONB NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS shared_at TIMESTAMPTZ;

-- Partial unique index for fast token lookups (only non-null tokens)
CREATE UNIQUE INDEX IF NOT EXISTS idx_threads_share_token
  ON conversation_threads(share_token) WHERE share_token IS NOT NULL;
