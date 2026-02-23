-- Migration: Add user_oauth_tokens table for OAuth-connected providers (e.g. Codex)

CREATE TABLE IF NOT EXISTS user_oauth_tokens (
  user_id       TEXT NOT NULL,
  provider      TEXT NOT NULL,
  access_token  BYTEA NOT NULL,
  refresh_token BYTEA NOT NULL,
  account_id    TEXT NOT NULL,
  email         TEXT,
  plan_type     TEXT,
  expires_at    TIMESTAMPTZ NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, provider)
);
