-- Migration 009: Add external thread identity for channel integrations
-- Allows ginlix-integration to pass a stable external_id (e.g. "telegram:12345:42")
-- so langalpha can resolve threads by external identity instead of requiring Redis mappings.

ALTER TABLE conversation_threads
    ADD COLUMN IF NOT EXISTS external_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS platform    VARCHAR(50);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_threads_external
    ON conversation_threads (platform, external_id)
    WHERE external_id IS NOT NULL;
