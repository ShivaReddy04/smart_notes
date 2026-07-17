"""add AI fields (category, priority) to notes

Why this file exists:
    The second migration. It evolves the schema to match the updated Note
    model by adding the AI-derived `category` and `priority` columns to the
    existing `notes` table. It chains onto the initial migration, so
    `alembic upgrade head` applies it after 0001.

    Key detail: both columns are added as NOT NULL WITH a server default.
    Adding a NOT NULL column to a table that may already contain rows
    requires a default to backfill those rows — otherwise the migration
    fails. The defaults ('Other' / 'Medium') match both the model and the
    AI fallback, so existing notes become valid immediately.

Revision ID: 0002_add_note_ai_fields
Revises: 0001_initial_schema
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Revision identifiers. This migration's parent is the initial schema.
revision: str = "0002_add_note_ai_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the category and priority columns to the notes table.

    server_default backfills any pre-existing rows so the NOT NULL
    constraint can be satisfied without error.
    """
    op.add_column(
        "notes",
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default="Other",
        ),
    )
    op.add_column(
        "notes",
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default="Medium",
        ),
    )


def downgrade() -> None:
    """Remove the AI columns (reverse order)."""
    op.drop_column("notes", "priority")
    op.drop_column("notes", "category")
