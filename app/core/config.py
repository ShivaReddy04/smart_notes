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
    # All vector tunables live here (never hardcoded). The embedding service,
    # the pgvector store, and search read these values.
    #
    # We use a HOSTED embedding API instead of an on-device model: local
    # sentence-transformers pulls in torch (~2 GB RAM) and does not fit a
    # free-tier container. The call goes through langchain-openai's
    # OpenAIEmbeddings pointed at an OpenAI-COMPATIBLE endpoint — Google
    # Gemini by default — so switching providers is a base-url + model +
    # dimensions change with no code edit.

    # Required: the embeddings API key. Like the other credentials there is no
    # safe default, so the app refuses to start until it is provided. For the
    # default Gemini endpoint this is a (free) Google AI Studio key.
    embedding_api_key: str

    # The OpenAI-compatible embeddings endpoint. Defaults to Gemini's; override
    # to point at OpenAI ("https://api.openai.com/v1") or any compatible host.
    embedding_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # The embedding model slug. Defaulted to Gemini's text-embedding-004.
    # Changing it may change the vector dimensionality (see below), which
    # requires re-embedding existing notes.
    embedding_model: str = "text-embedding-004"

    # Dimensionality of the vectors this model emits. MUST match the pgvector
    # column width in the note_embeddings table (migration 0004). Gemini's
    # text-embedding-004 emits 768; OpenAI text-embedding-3-small emits 1536.
    # Changing this requires a migration to resize the column and a re-embed.
    embedding_dimensions: int = 768

    # Bounded per-call timeout (seconds) so a slow/hung embeddings API cannot
    # stall a request indefinitely.
    embedding_timeout: float = 30.0

    # Default number of results returned by semantic search (the /search
    # endpoint may override this per request).
    search_top_k: int = 5

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
    # Notes can carry attached images (reference screenshots/photos). Only
    # metadata goes in the DB; the bytes go to a storage backend selected here.
    # These tunables are declared once so the storage service, the static mount
    # in main.py, the upload validation, and the URL builder all agree.

    # Which storage backend holds the image bytes:
    #   * "local" -> local disk under media_dir, served by StaticFiles (dev).
    #   * "s3"    -> any S3-compatible object storage (production). Works with
    #     Supabase Storage, Cloudflare R2, AWS S3, MinIO, etc.
    # The free tier has no persistent disk, so deployments set this to "s3".
    image_storage_backend: str = "local"

    # Filesystem directory where uploaded image bytes are stored when the
    # backend is "local". Kept at the PROJECT ROOT, NOT inside the app/ package:
    # app/ is source code, while uploads are runtime data. Ignored under "s3".
    media_dir: str = "./media"

    # --- S3-compatible object storage (used when backend == "s3") --------
    # boto3 speaks the S3 API that Supabase Storage / R2 / AWS all expose. These
    # are blank by default (local dev needs none) and set in the deployment env.
    #
    #   * endpoint  -> the provider's S3 endpoint, e.g. for Supabase:
    #                  https://<project_ref>.supabase.co/storage/v1/s3
    #                  (R2: https://<account_id>.r2.cloudflarestorage.com)
    #   * region    -> the provider's region. Supabase/AWS require a real value
    #                  (shown in the Supabase Storage settings, e.g. us-east-1);
    #                  R2 ignores it but the S3 client still needs one ("auto").
    #   * bucket    -> the bucket that holds the image objects (must be PUBLIC
    #                  for the public URLs below to be readable).
    #   * public base URL -> where objects are publicly readable. The image
    #     schema builds each image's URL as "<public base>/<stored filename>",
    #     so a client loads it straight from the provider's CDN; the API never
    #     proxies image bytes. For a Supabase public bucket this is:
    #       https://<project_ref>.supabase.co/storage/v1/object/public/<bucket>
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = ""
    s3_public_base_url: str = ""

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
