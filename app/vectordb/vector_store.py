"""app/vectordb/vector_store.py

Why this file exists:
    The vector-CRUD layer — the ONLY module that reads and writes note vectors.
    It exposes exactly three verbs over the `note_embeddings` table: upsert,
    delete, and query. Where the model file (note_embedding.py) answers "what
    shape is a stored vector", this file answers "what do we do with it".

    Storage backend — Postgres + pgvector (not Chroma):
        Vectors live in the same Postgres database as the notes, so semantic
        search needs no separate service and no persistent disk. Nearest
        neighbours are found with pgvector's cosine-distance operator, and the
        note metadata + text come from a JOIN to the `notes` table — so the
        vector row stores ONLY the embedding, never a duplicate of the note.

    Session ownership:
        Unlike the note write/read paths (which receive a request-scoped
        Session), this layer opens its OWN short-lived Session per operation
        via the injected session factory (SessionLocal by default). That keeps
        the existing accessor signatures intact — search.py still depends on a
        plain get_vector_store() with no session argument — and preserves the
        "vector index is a best-effort side store" design: a vector write runs
        in its own transaction and can fail without touching the note's.

    Two intentional design decisions carried over:
        * note_id is the vector's identity. Anchoring the row to the Postgres
          primary key makes sync trivial: an update is an upsert on the same
          note_id, a delete is a delete by it — no existence bookkeeping.
        * This layer raises on failure. The best-effort "never crash CRUD"
          behavior lives one layer up in note_embedding_service, so the search
          path (which must know when a query fails) is never handed a silent
          empty result.

    How it interacts with the rest of the app:
        * note_embedding_service (write side) calls upsert / delete.
        * search.py (read side) calls query and converts the returned
          distances into ranked SearchResults.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ai.embedding_models import VectorMetadata
from app.core.database import SessionLocal
from app.models.note import Note
from app.models.note_embedding import NoteEmbedding

logger = logging.getLogger("ai_smart_notes.vectordb")


def _iso(value: datetime | None) -> str:
    """Render a datetime as an ISO-8601 string for VectorMetadata.

    VectorMetadata keeps timestamps as strings (a contract inherited from the
    Chroma era, still convenient for the search API). Guards None defensively
    even though the columns are NOT NULL.
    """
    return value.isoformat() if value is not None else ""


class VectorQueryHit(BaseModel):
    """One raw hit returned by `VectorStore.query`.

    The typed metadata for the matched note, the note's text, and the raw
    cosine distance (lower == closer). It deliberately stops short of a
    SearchResult — turning `distance` into a similarity percentage is search.py's
    job. Building this from a joined (Note, distance) row happens in exactly one
    place (`query`), so no other module knows the query's shape.
    """

    metadata: VectorMetadata = Field(description="Typed metadata of the matched note.")
    document: str | None = Field(default=None, description="Stored note text, if any.")
    distance: float = Field(description="Cosine distance to the query (lower is closer).")


class VectorStore:
    """CRUD operations over the `note_embeddings` table.

    Stateless apart from an injected session factory. Injecting the factory
    (rather than importing SessionLocal directly in each method) keeps the
    class unit-testable with a factory bound to a test database.
    """

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def upsert(self, note_id: int, embedding: list[float]) -> None:
        """Insert or overwrite the vector for a single note.

        Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE so re-indexing a
        changed note overwrites the same note_id rather than raising on a
        duplicate. The note's metadata/text are NOT stored here — search reads
        them by joining `notes`, so there is nothing to keep in sync.
        """
        logger.debug("Upserting vector for note_id=%s", note_id)
        stmt = pg_insert(NoteEmbedding).values(note_id=note_id, embedding=embedding)
        stmt = stmt.on_conflict_do_update(
            index_elements=[NoteEmbedding.note_id],
            set_={"embedding": embedding},
        )
        with self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    def delete(self, note_id: int) -> None:
        """Remove a note's vector by note_id.

        Deleting a non-existent id is a no-op, which is exactly what we want: a
        delete stays safe and idempotent even if the note was never indexed
        (e.g. it was created while the embeddings API was unavailable). Note the
        FK's ON DELETE CASCADE already removes the vector when the note itself
        is deleted; this explicit path covers callers that delete by id.
        """
        logger.debug("Deleting vector for note_id=%s", note_id)
        with self._session_factory() as session:
            session.execute(sql_delete(NoteEmbedding).where(NoteEmbedding.note_id == note_id))
            session.commit()

    def query(self, embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        """Find the `top_k` nearest note vectors to a query embedding.

        Orders by pgvector's cosine distance (`<=>`) and joins `notes` so each
        hit carries the note's live metadata and text in one round-trip. Because
        the metadata comes from the notes table (not a copy frozen at index
        time), search results always reflect the note's current title/category.
        """
        logger.debug("Querying %d nearest vectors", top_k)
        distance = NoteEmbedding.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(Note, distance)
            .join(NoteEmbedding, NoteEmbedding.note_id == Note.id)
            .order_by(distance)
            .limit(top_k)
        )

        hits: list[VectorQueryHit] = []
        with self._session_factory() as session:
            for note, dist in session.execute(stmt).all():
                metadata = VectorMetadata(
                    note_id=note.id,
                    title=note.title,
                    category=note.category,
                    priority=note.priority,
                    created_at=_iso(note.created_at),
                    updated_at=_iso(note.updated_at),
                )
                hits.append(
                    VectorQueryHit(
                        metadata=metadata,
                        document=note.content,
                        distance=float(dist),
                    )
                )
        logger.debug("Query returned %d hit(s)", len(hits))
        return hits


# Module-level singleton, populated lazily so importing this module never opens
# a database session.
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the process-wide VectorStore, building it once.

    Cached so the factory-backed store is resolved a single time per process,
    mirroring get_embedding_service(). Callers (the write bridge and search)
    depend on this accessor, not on SessionLocal directly.
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
