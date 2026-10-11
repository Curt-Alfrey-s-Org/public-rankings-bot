"""Idempotent: add AuditLog ORM columns to legacy audit_log table.

Revision ID: 047
Revises: 046
Create Date: 2026-03-19

Older DBs created audit_log from database/schema_postgres.sql with
(actor_role, actor_subject, action, details, created_at) only.
Auth and admin_security use the SQLAlchemy AuditLog model (user_id, event_type,
ip_address, user_agent, success, timestamp). Without these columns, ORM queries
500 on GET /api/admin/login-attempts and /api/admin/security-metrics.

Does not drop legacy columns so postgres_manager.append_audit (rankings) keeps working.
"""

from alembic import op
from sqlalchemy import text

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'audit_log'
            ) THEN
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id INTEGER;
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS event_type VARCHAR(50);
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_agent VARCHAR(255);
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS success BOOLEAN DEFAULT TRUE;
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS "timestamp" TIMESTAMP;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = 'audit_log'
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.column_name = 'user_id'
                ) THEN
                    ALTER TABLE audit_log
                    ADD CONSTRAINT fk_audit_log_user_id_users
                    FOREIGN KEY (user_id) REFERENCES users(id);
                END IF;

                UPDATE audit_log SET "timestamp" = created_at
                WHERE "timestamp" IS NULL
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'audit_log'
                      AND column_name = 'created_at'
                  );

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'audit_log'
                      AND column_name = 'action'
                ) THEN
                    UPDATE audit_log
                    SET event_type = CASE
                        WHEN action::text = 'login' THEN 'login_success'
                        WHEN action::text = 'failed_login' THEN 'login_failed'
                        WHEN action::text LIKE '%failed%' THEN 'login_failed'
                        ELSE LEFT(action::text, 50)
                    END
                    WHERE event_type IS NULL;

                    UPDATE audit_log SET success = FALSE
                    WHERE action::text LIKE '%failed%';
                END IF;

                UPDATE audit_log SET "timestamp" = CURRENT_TIMESTAMP
                WHERE "timestamp" IS NULL;

                CREATE INDEX IF NOT EXISTS idx_user_id_timestamp
                ON audit_log (user_id, "timestamp");
                CREATE INDEX IF NOT EXISTS idx_event_type_timestamp
                ON audit_log (event_type, "timestamp");
            END IF;
        END $$;
    """
        )
    )


def downgrade():
    pass
