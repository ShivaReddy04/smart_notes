"""app/services/note_embedding_service.py

Why this file exists:
    The write-side bridge between the note domain and the vector subsystem.
    It is the mirror image of search.py: search.py reads, this writes. Given a
    Note ORM object it composes the text to embed, generates the embedding, and
    drives vector_store to index (or remove) the note. Its purpose is to give
    note_service ONE trivial call per lifecycle event while all the messy
    orchestration lives here.

    The defining responsibility — never raise (Feature 7):
        Postgres is the source of truth; the vector index is best-effort. So
        every public method here wraps its work in a catch-all that logs and
        swallows. If the embeddings API is down or the vector write fails, note
        create/update/delete must still succeed. Isolating that guarantee in
        this layer is the whole reason the bridge exists instead of
        note_service calling vector_store directly.

    Responsibility boundary:
        Note -> vector translation + best-effort orchestration. It does not
        embed text itself (embedding_service) or talk to Postgres/pgvector
        directly (vector_store); it sequences them and guarantees they can
        never break a CRUD operation.

    Note on metadata:
        Since vectors moved into Postgres, search reads a note's title,
        category, timestamps, and text by JOINing the `notes` table — so this
        bridge no longer builds or stores any metadata copy. It stores just the
        note_id -> embedding mapping.

    How it interacts with the rest of the app:
        * note_service (Feature 9) calls sync_note() on create/update and
          remove_note() on delete.
        * Depends on the shared EmbeddingService and VectorStore singletons.
"""

import logging

from app.ai.embedding_service import EmbeddingService, get_embedding_service
from app.models.note import Note
from app.vectordb.vector_store import VectorStore, get_vector_store

logger = logging.getLogger("ai_smart_notes.note_embedding")


def _compose_embedding_text(title: str, content: str | None) -> str:
    """Build the text that actually gets embedded from a note's fields.

    Both title and content carry semantic signal, so we join the non-empty
    parts (mirroring note_service._compose_text). Kept as a local helper rather
    than imported so this bridge stays decoupled from note_service.
    """
    parts = [part for part in (title, content) if part]
    return "\n\n".join(parts)


class NoteEmbeddingService:
    """Best-effort synchronization of notes into the vector index.

    Stateless apart from the two injected collaborators. Every method is
    guaranteed not to raise: failures are logged and swallowed so the vector
    index can never break a database operation.
    """

    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    def sync_note(self, note: Note) -> None:
        """Index or re-index a note's vector (used on create and update).

        Because vector_store.upsert is keyed on note_id, inserting a new note
        and updating an existing one are the same operation, so create and
        update share this single method. The embedding is computed from
        title + content for a richer signal. Any failure — a down embeddings
        API, a vector write error — is logged and swallowed (Feature 7).
        """
        try:
            text = _compose_embedding_text(note.title, note.content)
            embedding = self._embedding_service.embed_text(text)
            self._vector_store.upsert(note_id=note.id, embedding=embedding)
            logger.debug("Synced vector for note id=%s", note.id)
        except Exception:  # noqa: BLE001 — best-effort by design (Feature 7)
            # The vector index is not the source of truth; a failure here must
            # never fail the note's CRUD operation. Log with a stack trace and
            # move on — the note is safely persisted in Postgres regardless.
            logger.exception("Failed to sync vector for note id=%s; note is unaffected", note.id)

    def remove_note(self, note_id: int) -> None:
        """Remove a note's vector from the index (used on delete).

        Mirrors sync_note's contract: delete-by-id is idempotent and any
        failure is logged and swallowed so a vector-store outage cannot block a
        note deletion. (The FK cascade also drops the vector when the note row
        is deleted; this keeps deletion explicit and outage-tolerant.)
        """
        try:
            self._vector_store.delete(note_id)
            logger.debug("Removed vector for note id=%s", note_id)
        except Exception:  # noqa: BLE001 — best-effort by design (Feature 7)
            logger.exception(
                "Failed to remove vector for note id=%s; note is unaffected", note_id
            )


# Module-level singleton, populated lazily so importing this module never
# constructs the embedding client or opens a database session.
_note_embedding_service: NoteEmbeddingService | None = None


def get_note_embedding_service() -> NoteEmbeddingService:
    """Return the process-wide NoteEmbeddingService, building it once.

    Wires the shared EmbeddingService and VectorStore into the bridge. Cached
    per process, mirroring the other get_*() accessors. note_service depends on
    this accessor, not on the collaborators directly.
    """
    global _note_embedding_service
    if _note_embedding_service is None:
        _note_embedding_service = NoteEmbeddingService(
            get_embedding_service(), get_vector_store()
        )
    return _note_embedding_service
