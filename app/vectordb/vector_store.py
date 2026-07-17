"""app/vectordb/vector_store.py

Why this file exists:
    The vector-CRUD layer — the ONLY module that operates on the Chroma
    collection. It takes the collection handle from chroma_client and exposes
    exactly three verbs over it: upsert, delete, and query. Where
    chroma_client answers "how do we connect and where are vectors
    configured", this file answers "what do we do once connected".

    Responsibility boundary:
        Storage operations on note vectors, nothing more. It does not embed
        text (that is embedding_service), it does not decide sync policy from
        a Note ORM object (that is note_embedding_service), and it does not
        convert distances into similarity percentages (that is search.py).
        Its inputs are already-computed embeddings; its outputs are typed hits
        carrying the raw cosine distance.

    Two intentional design decisions:
        * id == str(note_id). Anchoring the Chroma id to the Postgres primary
          key is what makes sync trivial (Feature 5): an update is just an
          upsert over the same id, and a delete is a delete by that id — no
          existence bookkeeping required.
        * This layer raises on failure. The best-effort "never crash CRUD"
          behavior lives one layer up in note_embedding_service (Feature 7).
          Keeping vector_store honest means the search path, which genuinely
          needs to know when a query fails, is never handed a silent empty
          result.

    How it interacts with the rest of the app:
        * note_embedding_service (write side) calls upsert / delete.
        * search.py (read side) calls query and converts the returned
          distances into ranked SearchResults.
"""

import logging

from pydantic import BaseModel, Field

from app.ai.embedding_models import VectorMetadata
from app.vectordb.chroma_client import get_note_collection
from chromadb.api.models.Collection import Collection

logger = logging.getLogger("ai_smart_notes.vectordb")


def _vector_id(note_id: int) -> str:
    """Map a note's primary key to its Chroma vector id.

    Centralized so the "id is the stringified note_id" rule (Feature 5) is
    stated once. Every operation — upsert, delete, and hit-parsing — goes
    through this, so the convention can never drift between call sites.
    """
    return str(note_id)


class VectorQueryHit(BaseModel):
    """One raw hit returned by `VectorStore.query`.

    This is the vector store's output contract: the typed metadata for the
    matched note, the note's stored document text, and the raw cosine
    distance (lower == closer). It deliberately stops short of a
    SearchResult — turning `distance` into a similarity percentage is
    search.py's job (Feature 4). Parsing Chroma's nested response into this
    shape happens in exactly one place (`query`), so no other module needs
    to know Chroma's list-of-lists layout.
    """

    metadata: VectorMetadata = Field(description="Typed metadata of the matched note.")
    document: str | None = Field(default=None, description="Stored note text, if any.")
    distance: float = Field(description="Cosine distance to the query (lower is closer).")


class VectorStore:
    """CRUD operations over the Chroma notes collection.

    Stateless apart from the injected collection handle. Each method is a
    thin, well-typed wrapper around the Chroma API that enforces our
    conventions (string ids, single-query parsing) so callers stay free of
    Chroma-specific detail.
    """

    def __init__(self, collection: Collection) -> None:
        self._collection = collection

    def upsert(
        self,
        note_id: int,
        embedding: list[float],
        metadata: VectorMetadata,
        document: str,
    ) -> None:
        """Insert or overwrite the vector for a single note.

        `upsert` (not `add`) is what makes updates idempotent: re-indexing a
        changed note writes over the same id rather than raising on a
        duplicate. `metadata.to_chroma()` yields the primitives-only dict
        Chroma requires, and `document` stores the note text so search can
        return it without a second Postgres round-trip.
        """
        vector_id = _vector_id(note_id)
        logger.debug("Upserting vector id=%s", vector_id)
        self._collection.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            metadatas=[metadata.to_chroma()],
            documents=[document],
        )

    def delete(self, note_id: int) -> None:
        """Remove a note's vector by id.

        Deleting a non-existent id is a Chroma no-op, which is exactly the
        behavior we want: a delete stays safe and idempotent even if the note
        was never indexed (e.g. it was created while Chroma was unavailable).
        """
        vector_id = _vector_id(note_id)
        logger.debug("Deleting vector id=%s", vector_id)
        self._collection.delete(ids=[vector_id])

    def query(self, embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        """Find the `top_k` nearest note vectors to a query embedding.

        Chroma returns parallel list-of-lists keyed by request (ids,
        distances, metadatas, documents), each outer list having one entry
        per query embedding. We send a single embedding, so we read index
        [0] of each and zip them into typed VectorQueryHit rows. Missing
        includes are defended with `or []` so an empty collection yields an
        empty list rather than a KeyError.
        """
        logger.debug("Querying %d nearest vectors", top_k)
        response = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

        # Each key maps to a list-of-lists; [0] selects results for our one
        # query. Guard every access so a partial/empty response is safe.
        metadatas = (response.get("metadatas") or [[]])[0]
        documents = (response.get("documents") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]

        hits: list[VectorQueryHit] = []
        for raw_metadata, document, distance in zip(metadatas, documents, distances):
            hits.append(
                VectorQueryHit(
                    metadata=VectorMetadata.from_chroma(raw_metadata),
                    document=document,
                    distance=float(distance),
                )
            )
        logger.debug("Query returned %d hit(s)", len(hits))
        return hits


# Module-level singleton, populated lazily so importing this module never
# builds a Chroma client.
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the process-wide VectorStore, building it once.

    Wires the collection from chroma_client into a VectorStore. Cached so the
    handle is resolved a single time per process, mirroring
    get_embedding_service(). Callers (the write bridge and search) depend on
    this accessor, not on Chroma directly.
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(get_note_collection())
    return _vector_store
