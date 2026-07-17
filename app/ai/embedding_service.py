"""app/ai/embedding_service.py

Why this file exists:
    The text -> vector engine. It turns text into an embedding vector by
    calling a HOSTED embeddings API (Google Gemini by default) through
    langchain-openai's OpenAIEmbeddings client.

    Why hosted and not on-device:
        The previous implementation loaded sentence-transformers, which pulls
        in PyTorch (~2 GB RAM) and cannot run on a free-tier container. Moving
        the compute to a remote OpenAI-compatible endpoint removes torch
        entirely: the process stays tiny, and swapping providers is a
        base-url + model + dimensions change in config, not a code edit.

    Responsibility boundary:
        Embedding generation ONLY. It knows nothing about pgvector, notes, or
        the database — it is a pure function from text to a vector. That
        isolation means changing the embedding provider touches just this file
        and config; no caller needs to know.

    How it interacts with the rest of the app:
        * note_embedding_service calls `embed_text` to index a note.
        * search.py calls `embed_query` to embed an incoming search query.
        Both receive a plain `list[float]` ready to hand to the vector store.
"""

import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from app.core.config import get_settings

logger = logging.getLogger("ai_smart_notes.embeddings")


@lru_cache
def _load_client() -> OpenAIEmbeddings:
    """Build the embeddings client once and cache it.

    OpenAIEmbeddings holds an HTTP client and config; constructing it per call
    would be wasteful, so we build it lazily on first use and reuse it. It talks
    to whatever OpenAI-compatible endpoint `embedding_base_url` points at
    (Gemini by default).

    `check_embedding_ctx_length=False` disables OpenAIEmbeddings' tiktoken-based
    input splitting. That splitting assumes OpenAI's tokenizer, which does not
    match third-party endpoints like Gemini; turning it off sends our text
    through verbatim and avoids tokenizer-mismatch errors.
    """
    settings = get_settings()
    logger.info(
        "Initializing embeddings client model='%s' endpoint='%s'",
        settings.embedding_model,
        settings.embedding_base_url,
    )
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        # Request exactly `embedding_dimensions` values. gemini-embedding-001
        # emits 3072 by default but supports Matryoshka truncation to 768/1536;
        # this keeps the vector matching the pgvector column width. (Cosine
        # search normalizes internally, so truncated vectors are fine.)
        dimensions=settings.embedding_dimensions,
        timeout=settings.embedding_timeout,
        check_embedding_ctx_length=False,
    )


class EmbeddingService:
    """Generates embedding vectors from text via a hosted embeddings API.
    Stateless apart from the shared, cached client instance."""

    def __init__(self, client: OpenAIEmbeddings) -> None:
        self._client = client

    def embed_text(self, text: str) -> list[float]:
        """Embed note text (title + content) for indexing."""
        return self._client.embed_documents([text])[0]

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query.

        Uses the client's dedicated query path. For symmetric models this is
        identical to `embed_text`, but keeping it separate preserves clear call
        sites and future flexibility (e.g. an asymmetric query/passage model).
        """
        return self._client.embed_query(query)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Build (once) and return the shared EmbeddingService.

    Cached so the underlying HTTP client is created a single time per process.
    Tests can call `get_embedding_service.cache_clear()` (and
    `_load_client.cache_clear()`) to reset.
    """
    return EmbeddingService(_load_client())
