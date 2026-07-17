"""app/vectordb/chroma_client.py

Why this file exists:
    The connection layer to ChromaDB — and only that. It builds a persistent
    Chroma client (backed by local disk) and returns the single collection
    that holds note vectors, configured for cosine distance. Nothing here
    reads, writes, or queries vectors; that behavior lives one layer up in
    vector_store.py.

    Responsibility boundary:
        "How we connect and where vectors are configured" — persist path,
        collection name, and the cosine distance metric — is decided here in
        exactly one place. This is a LEAF module: it imports only chromadb and
        the app settings. It knows nothing about notes, the database, or how
        embeddings are produced, so higher layers can depend on it freely
        without dragging in the rest of the domain.

    How it interacts with the rest of the app:
        * vector_store.py calls `get_note_collection()` to obtain the handle
          it uses for upsert / delete / query.
        * The client and collection are cached (built once per process),
          mirroring the @lru_cache + get_*() idiom used by embedding_service.
"""

import logging

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import get_settings

logger = logging.getLogger("ai_smart_notes.vectordb")

# Chroma reads the distance metric from a reserved metadata key on the
# collection. We use cosine because our embeddings are unit-normalized
# (see embedding_service._encode), which makes cosine the natural, clean
# similarity measure for the search layer to convert into a percentage.
_DISTANCE_METRIC = "cosine"


def _build_client() -> ClientAPI:
    """Construct the persistent Chroma client.

    A PersistentClient stores its data on local disk at the configured
    path (creating the directory if it does not yet exist), so vectors
    survive process restarts. This is intentionally a plain function so it
    can be wrapped by the cached accessor below; construction is done once
    per process, not on every call.
    """
    settings = get_settings()
    logger.info("Opening Chroma persistent client at '%s'", settings.chroma_persist_path)
    return chromadb.PersistentClient(path=settings.chroma_persist_path)


def get_client() -> ClientAPI:
    """Return the process-wide persistent Chroma client, building it once.

    Cached module-level state (rather than @lru_cache) keeps the accessor's
    signature clean; the client is effectively a singleton for the app's
    lifetime. Tests can reset it via `reset_client()`.
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def get_note_collection() -> Collection:
    """Return the cosine-distance collection that stores note vectors.

    Uses get_or_create so first run provisions the collection (applying the
    cosine metric) and subsequent runs reuse the existing one. Two choices
    are made deliberately here:

      * embedding_function=None — embeddings are produced by our own
        EmbeddingService and passed in explicitly at write/query time. We do
        NOT want Chroma's built-in default embedder (which would download a
        second model and silently re-embed our text), so we disable it.

      * metadata={"hnsw:space": "cosine"} — sets the distance metric. Note
        this only takes effect when the collection is first created; an
        already-existing collection keeps whatever metric it was made with.
    """
    global _collection
    if _collection is None:
        settings = get_settings()
        client = get_client()
        logger.info(
            "Getting or creating Chroma collection '%s' (metric=%s)",
            settings.chroma_collection_name,
            _DISTANCE_METRIC,
        )
        _collection = client.get_or_create_collection(
            name=settings.chroma_collection_name,
            embedding_function=None,
            metadata={"hnsw:space": _DISTANCE_METRIC},
        )
    return _collection


def reset_client() -> None:
    """Drop the cached client and collection handles.

    Why: tests (or a config change) may need a fresh client pointed at a
    different persist path. Clearing these globals forces the next accessor
    call to rebuild. This does NOT delete any on-disk data — it only resets
    the in-process handles.
    """
    global _client, _collection
    _client = None
    _collection = None


# Module-level singletons, populated lazily by the accessors above so that
# merely importing this module never touches the disk or builds a client.
_client: ClientAPI | None = None
_collection: Collection | None = None
