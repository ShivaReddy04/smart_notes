"""app/core/config.py

Why this file exists:
    Centralizes all application configuration in one type-safe place.
    Instead of scattering os.getenv(...) calls throughout the codebase
    (which fail silently and return None), we declare every setting once
    with a type. pydantic-settings then validates them at startup, so a
    missing or malformed value crashes the app immediately and loudly
    rather than causing a confusing error deep in a request handler.

    This object is imported wherever configuration is needed (database
    engine, future AI providers, CORS, etc.), giving us a single source
    of truth that follows the Dependency Inversion principle: modules
    depend on this abstraction, not on raw environment access.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings loaded from the environment.

    Every field is a required or defaulted setting with an explicit type.
    pydantic-settings reads values from real environment variables first,
    then from a local .env file (useful for development).
    """

    # --- Application metadata ---
    # Why: surfaced in docs and logs; lets us version the API cleanly.
    app_name: str = "AI Smart Notes"
    app_version: str = "0.1.0"
    debug: bool = False

    # --- API configuration ---
    # Why: all routes are mounted under this prefix so we can evolve the
    # API (v2, etc.) without breaking existing clients.
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    # Why: a single SQLAlchemy-compatible URL. No default is provided
    # because there is no safe default for a production database; the app
    # must be told explicitly, and pydantic will error if it is absent.
    database_url: str

    # --- AI / OpenRouter (Phase 2) ---
    # Why these live here: the LLM client must not read os.environ directly.
    # Declaring the settings once, with types, means a missing key fails
    # loudly at startup rather than deep inside the first request.

    # Required: the OpenRouter API key. Like database_url there is no safe
    # default, so the app refuses to start until it is provided. (Phase 2
    # treats AI categorization as part of note creation, so the key is a
    # hard requirement, not optional.)
    openrouter_api_key: str

    # The model slug to use, in OpenRouter's "vendor/model" form. Defaulted
    # to a cheap, fast, JSON-reliable model but fully overridable, so you
    # can switch models (e.g. anthropic/claude-3.5-haiku) with no code
    # change.
    openrouter_model: str = "openai/gpt-4o-mini"

    # OpenRouter's OpenAI-compatible endpoint. Overridable for flexibility.
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Deterministic output for classification: temperature 0 yields stable,
    # repeatable category/priority predictions for the same input.
    llm_temperature: float = 0.0

    # Bounded per-call timeout (seconds) so a slow or hung LLM cannot stall
    # a request indefinitely; on timeout the categorizer falls back to
    # safe defaults.
    llm_timeout: float = 30.0

    # --- Embeddings & vector search (Phase 3) ---
    # Per Feature 6, all vector tunables live here (never hardcoded). The
    # embedding service, Chroma client, and search read these values.

    # The sentence-transformers model used to embed notes and queries.
    # Overridable, but note: changing it changes the vector dimensionality,
    # which requires re-indexing existing vectors.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Where ChromaDB persists vectors on local disk (spec: persist locally).
    # Relative to the project root by default.
    chroma_persist_path: str = "./chroma_data"

    # Name of the Chroma collection that holds note vectors.
    chroma_collection_name: str = "notes"

    # Default number of results returned by semantic search (the /search
    # endpoint may override this per request).
    search_top_k: int = 5

    # Device sentence-transformers runs on: "cpu" (universal default) or
    # "cuda" if a compatible GPU is available.
    embedding_device: str = "cpu"

    # --- Frontend / CORS (Phase 5) ---
    # Origins the browser SPA is served from and therefore allowed to call this
    # API cross-origin. A list so several origins can be permitted at once (e.g.
    # the Vite dev server now, the deployed site later). The default covers the
    # local Vite dev server on both localhost and 127.0.0.1; override in
    # production with the real deployed origin. Because this is a complex
    # (list) field, pydantic-settings expects a JSON array when set via the
    # environment, e.g. CORS_ORIGINS=["https://notes.example.com"].
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Image uploads (Phase 5) ---
    # Notes can carry attached images (reference screenshots/photos). The bytes
    # live on local disk and are served as static files; only metadata goes in
    # the DB. These tunables are declared here, never hardcoded, so the storage
    # service, the static mount in main.py, and the upload validation all read
    # one source of truth — and so a deployment can override them via env.

    # Filesystem directory where uploaded image bytes are stored. Kept at the
    # PROJECT ROOT (a sibling of ./chroma_data), NOT inside the app/ package:
    # app/ is source code, while uploads are runtime data. In Docker this
    # directory is a mounted volume so images survive container redeploys,
    # exactly like the Chroma vector store.
    media_dir: str = "./media"

    # URL path prefix under which the stored images are served (main.py mounts
    # StaticFiles here). An image saved as <media_dir>/<filename> is reachable
    # at <media_url_prefix>/<filename>; the image schema builds its public URL
    # from this value, so changing the mount point needs no code changes.
    media_url_prefix: str = "/media"

    # Hard cap on a single uploaded image, in bytes (default 5 MB). Enforced by
    # the storage service so a client cannot exhaust disk with one huge file.
    max_image_bytes: int = 5 * 1024 * 1024

    # Whitelist of accepted image MIME types. Anything else is rejected with a
    # 400 before it touches the disk. A list, so (like cors_origins) it must be
    # given as a JSON array when overridden via the environment.
    allowed_image_types: list[str] = [
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    ]

    # SettingsConfigDict tells pydantic where/how to load values.
    #   env_file        -> read a local .env during development
    #   case_sensitive  -> False so DATABASE_URL maps to database_url
    #   extra="ignore"  -> tolerate unrelated vars in the environment
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Why cached:
        Settings are immutable for the lifetime of the process, and
        re-reading/re-validating the environment on every access would be
        wasteful. lru_cache builds the object once and returns the same
        instance thereafter. This function is what other modules and
        FastAPI dependencies import, keeping construction in one place.
    """
    return Settings()
