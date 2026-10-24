"""Users, sessions, conversation ownership, and message metadata.

Revision ID: 0002_auth_sessions
Revises: 0001_foundation
Create Date: 2026-10-24
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0002_auth_sessions"
down_revision: Union[str, None] = "0001_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    op.add_column("conversations", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("title_source", sa.String(length=16), nullable=False, server_default="auto"),
    )
    op.add_column("conversations", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "messages",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="complete"),
    )
    op.add_column(
        "messages",
        sa.Column("extra", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )

    bind = op.get_bind()
    leftover = bind.execute(sa.text("SELECT COUNT(*) FROM conversations WHERE owner_id IS NULL")).scalar()
    if leftover:
        owner_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, display_name, role, is_active) "
                "VALUES (:id, :email, :password_hash, :display_name, :role, :is_active)"
            ),
            {
                "id": owner_id,
                "email": "migrated@raremed.local",
                "password_hash": "disabled",
                "display_name": "Migrated workspace",
                "role": "user",
                "is_active": False,
            },
        )
        bind.execute(
            sa.text("UPDATE conversations SET owner_id = :owner_id WHERE owner_id IS NULL"),
            {"owner_id": owner_id},
        )

    op.alter_column("conversations", "owner_id", nullable=False)
    op.create_foreign_key(
        "fk_conversations_owner_id_users",
        "conversations",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_conversations_owner_updated", "conversations", ["owner_id", "updated_at"])
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    inspector = inspect(bind)
    _ = inspector


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_column("messages", "extra")
    op.drop_column("messages", "status")
    op.drop_index("ix_conversations_owner_updated", table_name="conversations")
    op.drop_constraint("fk_conversations_owner_id_users", "conversations", type_="foreignkey")
    op.drop_column("conversations", "archived_at")
    op.drop_column("conversations", "title_source")
    op.drop_column("conversations", "owner_id")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
