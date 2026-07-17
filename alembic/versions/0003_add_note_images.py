"""add note_images table (attached images, Phase 5)

Why this file exists:
    The third migration. It evolves the schema to match the new NoteImage
    model by creating the `note_images` child table, which stores metadata
    for images attached to a note (the bytes live on disk, not in the DB).
    It chains onto 0002, so `alembic upgrade head` applies it last.

    Key details, mirrored from app/models/note_image.py:
      * A foreign key `note_id -> notes.id` with ON DELETE CASCADE, so
        deleting a note removes its image rows at the database level (not
        just via the ORM).
      * `note_id` is indexed — the one query we always run is "all images
        for this note".
      * `filename` has a UNIQUE index — the on-disk name is server-generated
        and must never collide.

Revision ID: 0003_add_note_images
Revises: 0002_add_note_ai_fields
Create Date: 2026-07-14
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Revision identifiers. This migration's parent is the AI-fields migration.
revision: str = "0003_add_note_images"
down_revision: Union[str, None] = "0002_add_note_ai_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the note_images table with its FK, index, and unique index."""
    op.create_table(
        "note_images",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Named FK with ON DELETE CASCADE so a deleted note takes its image
        # rows with it at the database level. Naming it keeps the downgrade
        # and any future ALTERs explicit.
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name="fk_note_images_note_id_notes",
            ondelete="CASCADE",
        ),
    )
    # Mirror index=True on the model's primary key.
    op.create_index("ix_note_images_id", "note_images", ["id"], unique=False)
    # Fast lookup of a note's images (the primary access pattern).
    op.create_index("ix_note_images_note_id", "note_images", ["note_id"], unique=False)
    # The on-disk filename is generated to be unique; enforce it in the DB too.
    op.create_index("ix_note_images_filename", "note_images", ["filename"], unique=True)


def downgrade() -> None:
    """Drop the note_images table (its indexes and FK go with it)."""
    op.drop_table("note_images")
