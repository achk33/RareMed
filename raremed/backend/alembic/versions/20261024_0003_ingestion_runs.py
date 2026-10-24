"""Import-run history for medical dataset ingestion.

Revision ID: 0003_ingestion_runs
Revises: 0002_auth_sessions
Create Date: 2026-10-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ingestion_runs"
down_revision: Union[str, None] = "0002_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("trigger", sa.String(length=16), nullable=False, server_default="cli"),
        sa.Column("strict", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed_dir", sa.String(length=500), nullable=True),
        sa.Column("imports_dir", sa.String(length=500), nullable=True),
        sa.Column("previous_run_key", sa.String(length=64), nullable=True),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_required", sa.JSON(), nullable=False),
        sa.Column("source_summaries", sa.JSON(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_key", name="uq_ingestion_runs_run_key"),
    )
    op.create_index("ix_ingestion_runs_created_at", "ingestion_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_created_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
