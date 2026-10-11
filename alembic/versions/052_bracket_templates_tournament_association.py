"""Bracket templates and tournament association / bracket metadata.

Revision ID: 052
Revises: 051
Create Date: 2026-04-10

Adds bracket_templates (director-saved and system presets). Adds tournaments.association,
tournaments.tournament_end_date, tournaments.bracket_template_id for wizard scoping.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import JSONB
import json
import logging

logger = logging.getLogger(__name__)

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def _se_rounds(draw_size: int):
    """Single-elimination round match counts (full draw)."""
    out = []
    m = draw_size // 2
    rnd = 1
    while m >= 1:
        out.append({"round": rnd, "matches": m})
        m //= 2
        rnd += 1
    return out


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)

    op.create_table(
        "bracket_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("player_count", sa.Integer(), nullable=False),
        sa.Column("bracket_draw_size", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("bye_strategy", sa.String(32), nullable=False, server_default="top_seed"),
        sa.Column("rounds", JSONB(), nullable=False),
        sa.Column("association", sa.String(64), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )
    op.create_foreign_key(
        "fk_bracket_templates_created_by_users",
        "bracket_templates",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )

    tcols = [c["name"] for c in insp.get_columns("tournaments")] if "tournaments" in insp.get_table_names() else []
    if "tournaments" in insp.get_table_names():
        if "association" not in tcols:
            op.add_column("tournaments", sa.Column("association", sa.String(64), nullable=True))
        if "tournament_end_date" not in tcols:
            op.add_column("tournaments", sa.Column("tournament_end_date", sa.Date(), nullable=True))
        if "bracket_template_id" not in tcols:
            op.add_column("tournaments", sa.Column("bracket_template_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_tournaments_bracket_template",
                "tournaments",
                "bracket_templates",
                ["bracket_template_id"],
                ["id"],
                ondelete="SET NULL",
            )

    seeds = [
        ("Single elimination — 16", 16, 16, "single_elimination", "none", _se_rounds(16), None),
        ("Single elimination — 32", 32, 32, "single_elimination", "none", _se_rounds(32), None),
        ("Single elimination — 64", 64, 64, "single_elimination", "none", _se_rounds(64), None),
        (
            "Single elimination — 80 (128 draw, byes)",
            80,
            128,
            "single_elimination",
            "top_seed",
            _se_rounds(128),
            None,
        ),
        ("Double elimination — 16", 16, 16, "double_elimination", "none", _se_rounds(16), None),
        ("Double elimination — 32", 32, 32, "double_elimination", "none", _se_rounds(32), None),
        ("Double elimination — 64", 64, 64, "double_elimination", "none", _se_rounds(64), None),
    ]
    for name, pc, bds, fmt, bye, rounds, assoc in seeds:
        conn.execute(
            text(
                """
                INSERT INTO bracket_templates
                (name, player_count, bracket_draw_size, format, bye_strategy, rounds, association, is_system, created_by)
                VALUES (:name, :pc, :bds, :fmt, :bye, (:rounds)::jsonb, :assoc, true, NULL)
                """
            ),
            {
                "name": name,
                "pc": pc,
                "bds": bds,
                "fmt": fmt,
                "bye": bye,
                "rounds": json.dumps(rounds),
                "assoc": assoc,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if "tournaments" in insp.get_table_names():
        tcols = [c["name"] for c in insp.get_columns("tournaments")]
        if "bracket_template_id" in tcols:
            op.drop_constraint("fk_tournaments_bracket_template", "tournaments", type_="foreignkey")
            op.drop_column("tournaments", "bracket_template_id")
        if "tournament_end_date" in tcols:
            op.drop_column("tournaments", "tournament_end_date")
        if "association" in tcols:
            op.drop_column("tournaments", "association")
    op.drop_table("bracket_templates")
