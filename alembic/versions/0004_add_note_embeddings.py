"""add note_embeddings table (pgvector semantic search)

Why this file exists:
    The fourth migration. It moves semantic-search vectors OUT of an on-disk
    Chroma store and INTO Postgres itself, using the `pgvector` extension. This
    is what lets the app run with no local vector service and no persistent
    disk (a free-tier requirement): the note text is embedded by a hosted API
    and the resulting vector is stored here, one row per note.

    What it does, mirrored from app/models/note_embedding.py:
      * Enables the `vector` extension (Neon and standard Postgres ship it;
        this is a no-op if already enabled).
      * Creates `note_embeddings(note_id PK -> notes.id ON DELETE CASCADE,
        embedding vector(768))`. The PK is also the FK, so each note has at
        most one embedding and deleting a note drops its vector automatically.
      * Adds an HNSW index using `vector_cosine_ops` so nearest-neighbour
        search by cosine distance stays fast as the table grows.

    Dimensionality note:
        768 matches Settings.embedding_dimensions (Gemini text-embedding-004).
        If you switch to a model with a different width, you must resize this
        column and re-embed every note.

    It chains onto 0003, so `alembic upgrade head` applies it last.

Revision ID: 0004_add_note_embeddings
Revises: 0003_add_note_images
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Revision identifiers. This migration's parent is the note-images migration.
revision: str = "0004_add_note_embeddings"
down_revision: Union[str, None] = "0003_add_note_images"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must equal Settings.embedding_dimensions. Kept as a literal here because a
# migration is a frozen historical record and must not import runtime config.
_EMBEDDING_DIMS = 768


def upgrade() -> None:
    """Enable pgvector and create the note_embeddings table + HNSW index."""
    # Provision the extension first; the vector column type depends on it.
    # IF NOT EXISTS makes re-runs and shared databases safe.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create the table with its key + FK. The `embedding` column is added
    # separately via raw SQL below, because its `vector(N)` type comes from the
    # pgvector extension and we deliberately avoid importing the pgvector
    # SQLAlchemy type inside a (frozen) migration.
    op.create_table(
        "note_embeddings",
        # note_id is BOTH the primary key and the foreign key: one embedding
        # per note, and no separate surrogate id is needed.
        sa.Column("note_id", sa.Integer(), primary_key=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
            name="fk_note_embeddings_note_id_notes",
            ondelete="CASCADE",
        ),
    )
    op.execute(f"ALTER TABLE note_embeddings ADD COLUMN embedding vector({_EMBEDDING_DIMS}) NOT NULL")

    # Approximate-nearest-neighbour index for cosine distance (the metric the
    # search layer uses). HNSW gives fast queries; it is built on the empty
    # table and maintained as rows are inserted.
    op.execute(
        "CREATE INDEX ix_note_embeddings_embedding "
        "ON note_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Drop the note_embeddings table (its index and FK go with it).

    The `vector` extension is intentionally left installed: other objects may
    rely on it, and dropping an extension is a heavier, riskier operation than
    this migration should own.
    """
    op.drop_table("note_embeddings")
