"""add users table + note/task ownership (Phase 6 auth)

Why this file exists:
    The fifth migration. It introduces authentication by:
      * creating the `users` table (email + bcrypt password hash), and
      * adding a nullable `user_id` foreign key to both `notes` and `tasks`,
        each with ON DELETE CASCADE and an index.

    Why `user_id` is NULLABLE: these tables may already hold rows (created
    before auth existed). A NOT NULL column could not be added to a populated
    table without a default owner, and there is none yet. So the column starts
    nullable; the application backfills existing rows to the FIRST account that
    registers (see app/services/auth_service.py), and every row created through
    the app sets the owner explicitly.

    It chains onto 0004, so `alembic upgrade head` applies it last.

Revision ID: 0005_add_users_and_ownership
Revises: 0004_add_note_embeddings
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Revision identifiers. This migration's parent is the embeddings migration.
revision: str = "0005_add_users_and_ownership"
down_revision: Union[str, None] = "0004_add_note_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create `users`, then add the `user_id` FK to `notes` and `tasks`."""
    # --- users table -------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    # Unique + indexed: one account per email, and fast lookup on every login.
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- ownership FK on notes --------------------------------------
    op.add_column("notes", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_notes_user_id_users",
        "notes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notes_user_id", "notes", ["user_id"], unique=False)

    # --- ownership FK on tasks --------------------------------------
    op.add_column("tasks", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_user_id_users",
        "tasks",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"], unique=False)


def downgrade() -> None:
    """Reverse the upgrade: drop the FKs/columns, then the users table."""
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_constraint("fk_tasks_user_id_users", "tasks", type_="foreignkey")
    op.drop_column("tasks", "user_id")

    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_constraint("fk_notes_user_id_users", "notes", type_="foreignkey")
    op.drop_column("notes", "user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
