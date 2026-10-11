"""Create rating_accuracy_metrics and player_rating_accuracy (historical accuracy tracking).

Revision ID: 053
Revises: 052
Create Date: 2026-05-06

Tables previously lived only in database/migrations/add_historical_rating_tracking.sql;
production uses Alembic-only upgrades, so the ORM/accuracy engine never saw these rows.
See api/services/rating_accuracy_engine.py.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade():
    # Match database/migrations/add_historical_rating_tracking.sql exactly:
    # PostgreSQL DOUBLE PRECISION (not SQL FLOAT) — see PG docs §8.1.3.
    op.create_table(
        "rating_accuracy_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("rating_type", sa.String(32), nullable=False),
        sa.Column("calculation_date", sa.Date(), nullable=False),
        sa.Column("total_predictions", sa.Integer(), server_default=sa.text("0")),
        sa.Column("accurate_predictions", sa.Integer(), server_default=sa.text("0")),
        sa.Column("mean_absolute_error", DOUBLE_PRECISION()),
        sa.Column("root_mean_squared_error", DOUBLE_PRECISION()),
        sa.Column("accuracy_percentage", DOUBLE_PRECISION()),
        sa.Column("confidence_interval_lower", DOUBLE_PRECISION()),
        sa.Column("confidence_interval_upper", DOUBLE_PRECISION()),
        sa.Column("sample_size", sa.Integer()),
        sa.Column(
            "last_updated",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "rating_type",
            "calculation_date",
            name="uq_rating_accuracy_metrics_type_date",
        ),
    )
    op.create_index(
        "idx_accuracy_metrics_type_date",
        "rating_accuracy_metrics",
        ["rating_type", "calculation_date"],
    )

    op.create_table(
        "player_rating_accuracy",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.String(255), nullable=False),
        sa.Column("player_name", sa.String(255), nullable=False),
        sa.Column("rating_type", sa.String(32), nullable=False),
        sa.Column("predicted_rating", DOUBLE_PRECISION(), nullable=False),
        sa.Column("actual_rating", DOUBLE_PRECISION()),
        sa.Column("absolute_error", DOUBLE_PRECISION()),
        sa.Column("accuracy_score", DOUBLE_PRECISION()),
        sa.Column("confidence_level", DOUBLE_PRECISION()),
        sa.Column("prediction_date", sa.Date(), nullable=False),
        sa.Column("verification_date", sa.Date()),
        sa.Column("data_source", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_player_accuracy_player_type",
        "player_rating_accuracy",
        ["player_id", "rating_type"],
    )
    op.create_index(
        "idx_player_accuracy_date",
        "player_rating_accuracy",
        ["prediction_date"],
    )


def downgrade():
    op.drop_index("idx_player_accuracy_date", table_name="player_rating_accuracy")
    op.drop_index("idx_player_accuracy_player_type", table_name="player_rating_accuracy")
    op.drop_table("player_rating_accuracy")
    op.drop_index("idx_accuracy_metrics_type_date", table_name="rating_accuracy_metrics")
    op.drop_table("rating_accuracy_metrics")
