"""app/models/note_embedding.py

Why this file exists:
    Defines the persistence shape of a note's semantic-search vector — the
    `note_embeddings` table — as a SQLAlchemy ORM model. Each note has at most
    one embedding, so this is a 1:1 child of `notes` whose primary key IS the
    foreign key back to it.

    Why the embedding lives in its own table (not a column on `notes`):
      * It is OPTIONAL and best-effort: a note is valid whether or not its
        vector was computed (the embeddings API may be down), so keeping it out
        of the notes row avoids a NULL vector column and a wider hot table.
      * It is written on a separate, best-effort path (note_embedding_service),
        mirroring how the old Chroma store was a side index rather than part of
        the note itself.

    Responsibility boundary (identical to every other model file):
      * It does NOT compute embeddings          -> that is embedding_service.
      * It does NOT run queries                  -> that is vector_store.
      * It holds only the vector + its note link.

    How it interacts with the rest of the app:
      * Inherits from `Base`, so importing this module (via app/db/base.py)
        registers the `note_embeddings` table on `Base.metadata`.
      * vector_store.py reads/writes instances; the delete cascades with the
        parent note at the database level.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.database import Base

# The vector width is fixed at class-definition time from config. It MUST match
# the pgvector column created in migration 0004; both derive from the embedding
# model's output dimensionality (Gemini text-embedding-004 = 768).
_EMBEDDING_DIMS = get_settings().embedding_dimensions


class NoteEmbedding(Base):
    """ORM model mapping the `note_embeddings` table (1:1 child of `notes`)."""

    __tablename__ = "note_embeddings"

    # --- Identity + parent link (same column) -------------------------
    # note_id is the primary key AND the foreign key: one embedding per note.
    # ondelete="CASCADE" pushes the delete rule down to Postgres, so removing a
    # note drops its embedding even via raw SQL or a bulk delete.
    note_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # --- The vector ---------------------------------------------------
    # pgvector's Vector type maps to the SQL `vector(N)` column. Distance
    # operators (cosine, L2, inner product) are used by vector_store.query.
    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBEDDING_DIMS), nullable=False)

    def __repr__(self) -> str:
        """Short representation for logs; omits the raw vector for brevity."""
        return f"<NoteEmbedding note_id={self.note_id!r} dims={_EMBEDDING_DIMS}>"
