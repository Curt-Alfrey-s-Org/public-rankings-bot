-- Fix audit_log table schema to match the AuditLog model
-- The model was updated but the database schema wasn't migrated

-- Rename existing columns to preserve data if needed
ALTER TABLE audit_log RENAME COLUMN actor_role TO old_actor_role;
ALTER TABLE audit_log RENAME COLUMN actor_subject TO old_actor_subject;
ALTER TABLE audit_log RENAME COLUMN action TO old_action;

-- Add new columns
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS event_type VARCHAR(50);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_agent VARCHAR(255);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS success BOOLEAN DEFAULT TRUE;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Migrate data from old columns to new columns (best effort)
UPDATE audit_log SET 
    event_type = CASE 
        WHEN old_action = 'login' THEN 'login_success'
        WHEN old_action = 'logout' THEN 'logout'
        WHEN old_action = 'failed_login' THEN 'login_failed'
        ELSE old_action
    END,
    success = CASE 
        WHEN old_action LIKE '%failed%' THEN FALSE
        ELSE TRUE
    END
WHERE event_type IS NULL;

-- Drop old columns
ALTER TABLE audit_log DROP COLUMN IF EXISTS old_actor_role;
ALTER TABLE audit_log DROP COLUMN IF EXISTS old_actor_subject;
ALTER TABLE audit_log DROP COLUMN IF EXISTS old_action;

-- Add indexes for the new schema
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id_timestamp ON audit_log (user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type_timestamp ON audit_log (event_type, timestamp);
