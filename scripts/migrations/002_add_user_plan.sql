-- Migration 002: Plans table + user plan_id FK + redemption codes system
-- Purpose: Move tier/plan definitions from config.yaml to DB for dynamic management

-- 1. Plans table (source of truth for tiers)
CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    rank INT NOT NULL DEFAULT 0,
    daily_credits NUMERIC(10,2) NOT NULL DEFAULT 500.0,
    max_active_workspaces INT NOT NULL DEFAULT 3,
    max_concurrent_requests INT NOT NULL DEFAULT 5,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_plans_default ON plans (is_default) WHERE is_default = TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_plans_rank ON plans (rank);

-- 2. Seed initial plans
INSERT INTO plans (name, display_name, rank, daily_credits, max_active_workspaces, max_concurrent_requests, is_default) VALUES
    ('free',       'Free',       0, 1000.0,  3,  5,  TRUE),
    ('pro',        'Pro',        1, 5000.0, 10, 20, FALSE),
    ('enterprise', 'Enterprise', 2, -1,    -1, -1, FALSE)
ON CONFLICT (name) DO NOTHING;

-- 3. Add plan_id FK to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_id INT;
UPDATE users SET plan_id = (SELECT id FROM plans WHERE is_default = TRUE LIMIT 1) WHERE plan_id IS NULL;
ALTER TABLE users ALTER COLUMN plan_id SET NOT NULL;
ALTER TABLE users ALTER COLUMN plan_id SET DEFAULT 1;
ALTER TABLE users ADD CONSTRAINT fk_users_plan FOREIGN KEY (plan_id) REFERENCES plans(id);
CREATE INDEX IF NOT EXISTS idx_users_plan_id ON users (plan_id);

-- 4. Redemption codes
CREATE TABLE IF NOT EXISTS redemption_codes (
    code VARCHAR(50) PRIMARY KEY,
    plan_id INT NOT NULL REFERENCES plans(id),
    max_redemptions INT NOT NULL DEFAULT 1,
    current_redemptions INT NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 5. Redemption history (plan names as strings for audit trail)
CREATE TABLE IF NOT EXISTS redemption_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL REFERENCES redemption_codes(code),
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON UPDATE CASCADE,
    previous_plan VARCHAR(50) NOT NULL,
    new_plan VARCHAR(50) NOT NULL,
    redeemed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(code, user_id)
);
CREATE INDEX IF NOT EXISTS idx_redemption_history_user ON redemption_history(user_id);
