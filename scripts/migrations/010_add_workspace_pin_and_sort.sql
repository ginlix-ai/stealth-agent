-- 010: Add workspace pinning and sort order
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_workspaces_user_pin_sort ON workspaces (user_id, is_pinned DESC, sort_order ASC);
