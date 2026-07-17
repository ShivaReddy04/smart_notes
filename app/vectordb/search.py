"""app/vectordb/search.py

Why this file exists:
    The read-side orchestrator for semantic search — the single place that
    turns a human query string into ranked SearchResults. It is the mirror
    image of the write bridge: it composes the three lower layers in order
    (embed the query, query the vector store, score + rank the hits) and owns
    the one responsibility none of them do — converting cosine distance into
    a similarity percentage (Feature 4).

    Responsibility boundary:
        Orchestration + scoring. It does not know how embeddings are computed
        (embedding_service) or how Chroma is queried (vector_store); it only
        sequences them and turns raw distances into ranked SearchResult DTOs.

    How it interacts with the rest of the app:
        * The /search route (Feature 10) calls `search()` with a query and an
          optional result limit, then serializes the returned SearchResults.
        * Unlike the write bridge, this path does NOT swallow errors: a failed
          search must surface to the caller (as an HTTP error), never masquerade
          as "no results".
"""

import logging

from app.ai.embedding_models import SearchResult
from app.ai.embedding_service import EmbeddingService, get_embedding_service
from app.core.config import get_settings
from app.vectordb.vector_store import VectorStore, get_vector_store

logger = logging.getLogger("ai_smart_notes.search")


def _distance_to_similarity(distance: float) -> int:
    """Convert a Chroma cosine distance into a 0-100 similarity percentage.

    Chroma reports cosine *distance* (0.0 == identical, larger == farther).
    Because our embeddings are unit-normalized, similarity is simply
    `1 - distance`. We scale to a percentage and clamp to [0, 100]: cosine
    similarity can be negative for unrelated vectors (distance > 1), and a
    negative percentage would be meaningless, so 0 is the floor. This is the
    only scoring logic in the vector subsystem, isolated here for easy
    testing.
    """
    similarity = 1.0 - distance
    score = round(similarity * 100)
    return max(0, min(100, score))


class SearchService:
    """Runs semantic search: embed the query, retrieve, score, and rank.

    Stateless apart from the two injected collaborators. Injecting them
    (rather than reaching for the module singletons directly) keeps the
    service unit-testable with fakes and follows the same DI shape used
    across the app.
    """

    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        """Return up to `top_k` notes most similar in meaning to `query`.

        Steps: guard empty input, embed the query, retrieve nearest vectors,
        convert each distance to a similarity percentage, and sort high→low.
        `top_k` falls back to the configured default when not supplied.
        """
        if not query or not query.strip():
            # Nothing to search for — skip the embedding + Chroma round-trip.
            logger.debug("Empty search query; returning no results")
            return []

        limit = top_k if top_k is not None else get_settings().search_top_k
        logger.debug("Searching (top_k=%d) for query of %d chars", limit, len(query))

        embedding = self._embedding_service.embed_query(query)
        hits = self._vector_store.query(embedding, limit)

        results = [
            SearchResult.from_hit(
                metadata=hit.metadata,
                content=hit.document,
                similarity_score=_distance_to_similarity(hit.distance),
            )
            for hit in hits
        ]

        # Feature 4 specifies ranked output; sort explicitly rather than
        # relying on the store's ordering as an implicit contract.
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        logger.debug("Search produced %d ranked result(s)", len(results))
        return results


# Module-level singleton, populated lazily so importing this module never
# constructs the embedding model or the Chroma client.
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    """Return the process-wide SearchService, building it once.

    Wires the shared EmbeddingService and VectorStore into a SearchService.
    Cached per process, mirroring the other get_*() accessors. The /search
    route depends on this accessor, not on the collaborators directly.
    """
    global _search_service
    if _search_service is None:
        _search_service = SearchService(get_embedding_service(), get_vector_store())
    return _search_service
