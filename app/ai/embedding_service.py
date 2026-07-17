"""app/ai/embedding_service.py

Why this file exists:
    The text -> vector engine. It wraps the sentence-transformers library,
    loads the configured model (all-MiniLM-L6-v2 by default), and turns text
    into embedding vectors.

    Responsibility boundary:
        Embedding generation ONLY. It knows nothing about ChromaDB, notes,
        or the database — it is a pure function from text to a vector. That
        isolation means changing the embedding model touches just this file
        and config; no caller needs to know.

    How it interacts with the rest of the app:
        * note_embedding_service calls `embed_text` to index a note.
        * search.py calls `embed_query` to embed an incoming search query.
        Both receive a plain `list[float]` ready to hand to ChromaDB.
"""

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger("ai_smart_notes.embeddings")


@lru_cache
def _load_model() -> SentenceTransformer:
    """Load the sentence-transformers model once and cache it.

    Lazy + cached: construction is expensive (it loads weights and may
    download them on first run), so we build it on first use and reuse the
    instance thereafter. Importing this module therefore never triggers a
    download.
    """
    settings = get_settings()
    logger.info(
        "Loading embedding model '%s' on device '%s'",
        settings.embedding_model,
        settings.embedding_device,
    )
    return SentenceTransformer(settings.embedding_model, device=settings.embedding_device)


class EmbeddingService:
    """Generates embedding vectors from text using a sentence-transformers
    model. Stateless apart from the shared, cached model instance."""

    def __init__(self, model: SentenceTransformer) -> None:
        self._model = model

    def embed_text(self, text: str) -> list[float]:
        """Embed note text (title + content) for indexing."""
        return self._encode(text)

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query. Identical encoding to `embed_text` for this
        symmetric model, but kept separate for clear call sites and future
        flexibility (e.g. swapping to an asymmetric query/passage model)."""
        return self._encode(query)

    def _encode(self, text: str) -> list[float]:
        """Run the model and return a plain Python list of floats.

        `normalize_embeddings=True` yields unit-length vectors — a common
        best practice that is harmless under cosine distance and keeps the
        similarity math clean. `.tolist()` converts the numpy output into
        the list form ChromaDB expects.
        """
        vector = self._model.encode(text, normalize_embeddings=True)
        result: list[float] = vector.tolist()
        logger.debug("Generated embedding (chars=%d, dims=%d)", len(text), len(result))
        return result


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Build (once) and return the shared EmbeddingService.

    Cached so the underlying model is loaded a single time per process.
    Tests can call `get_embedding_service.cache_clear()` (and
    `_load_model.cache_clear()`) to reset.
    """
    return EmbeddingService(_load_model())
