"""Self-calibration tables for Phase 4 (params + improvement log).

Revision ID: 060
Revises: 059
Create Date: 2026-07-12
"""

from alembic import op
from sqlalchemy import text

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS rating_calibration_params (
                id SERIAL PRIMARY KEY,
                rating_type VARCHAR(32) NOT NULL,
                parameter_name VARCHAR(64) NOT NULL,
                parameter_value DOUBLE PRECISION NOT NULL,
                effective_date DATE NOT NULL,
                calibration_method VARCHAR(64),
                sample_size INTEGER,
                confidence_interval DOUBLE PRECISION,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(rating_type, parameter_name, effective_date)
            )
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS system_accuracy_improvement (
                id SERIAL PRIMARY KEY,
                improvement_date DATE NOT NULL,
                rating_type VARCHAR(32) NOT NULL,
                previous_accuracy DOUBLE PRECISION,
                new_accuracy DOUBLE PRECISION,
                improvement_amount DOUBLE PRECISION,
                calibration_changes JSONB,
                sample_size INTEGER,
                statistical_significance DOUBLE PRECISION,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_calibration_params_type "
            "ON rating_calibration_params(rating_type, effective_date)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_accuracy_improvement_date "
            "ON system_accuracy_improvement(improvement_date)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS idx_accuracy_improvement_date"))
    op.execute(text("DROP INDEX IF EXISTS idx_calibration_params_type"))
    op.execute(text("DROP TABLE IF EXISTS system_accuracy_improvement"))
    op.execute(text("DROP TABLE IF EXISTS rating_calibration_params"))
