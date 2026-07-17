"""app/main.py

Why this file exists:
    The composition root of the application — the single place that wires
    everything together: it creates the FastAPI instance, mounts the
    routers, registers exception handlers, configures logging, and exposes
    a health check. It is the only module that legitimately depends on
    every layer, because assembly (not logic) is its whole purpose.

    It is also the ONE HTTP-aware place that turns domain exceptions into
    responses, fulfilling the contract set up in `utils/exceptions.py`:
    services raise framework-agnostic `AppError`s; here they become
    consistent JSON error bodies with the right status code.

    How it interacts with the rest of the app:
        * Imports settings for app metadata and the API prefix.
        * Includes the notes and tasks routers under that prefix.
        * Registers handlers so the whole app returns uniform errors.
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, note_images, notes, search, tasks
from app.core.config import get_settings
from app.utils.exceptions import AppError

# --- Logging ----------------------------------------------------------
# Configure logging once, at the composition root. The catch-all handler
# below uses this logger to record unexpected errors with full tracebacks,
# and Phase 2's AI-failure logging will reuse the same configuration.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("ai_smart_notes")

# Load validated settings once for app metadata and the API prefix.
settings = get_settings()

# --- Application instance ---------------------------------------------
# Title/version/debug come from settings so nothing is hardcoded and the
# values surface in the auto-generated docs at /docs.
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# --- CORS ------------------------------------------------------------
# The browser SPA (Phase 5) is served from a different origin than this API,
# so the browser blocks its requests unless we opt in here. We allow exactly
# the origins configured in settings (never "*" together with credentials,
# which browsers reject) and permit all methods/headers so every endpoint —
# including the JSON bodies and future auth headers — works from the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception handlers ----------------------------------------------
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Translate any expected domain error into a uniform JSON response.

    Because every AppError subclass carries a `status_code`, this single
    handler covers 404 (NotFoundError), 400 (BadRequestError), and any
    future domain error — no per-type branching required.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled (i.e. truly unexpected) errors.

    Logs the full traceback for debugging, but returns a generic 500 with
    NO internal detail, so stack traces and implementation specifics never
    leak to API clients.
    """
    logger.exception("Unhandled error during request to %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


# --- Routers ----------------------------------------------------------
# Mount each resource router under the configured API version prefix, so
# routes resolve to e.g. /api/v1/notes and /api/v1/tasks. The prefix is
# defined once in settings.
app.include_router(notes.router, prefix=settings.api_v1_prefix)
app.include_router(tasks.router, prefix=settings.api_v1_prefix)
# Phase 3: semantic search over notes, resolving to /api/v1/search.
app.include_router(search.router, prefix=settings.api_v1_prefix)
# Phase 4: chat-with-notes (RAG), resolving to /api/v1/chat.
app.include_router(chat.router, prefix=settings.api_v1_prefix)
# Phase 5: image attachments, resolving to /api/v1/notes/{id}/images.
app.include_router(note_images.router, prefix=settings.api_v1_prefix)


# --- Static media (Phase 5) ------------------------------------------
# Uploaded note images are served straight from disk at `media_url_prefix`
# (e.g. GET /media/<file>) ONLY when the local storage backend is active. The
# directory is created first because StaticFiles refuses to mount a path that
# does not exist — this guarantees a fresh checkout boots without a missing-dir
# error even before the first upload.
#
# On the "s3" backend the bytes live in S3-compatible storage (Supabase/R2/…)
# and are served from the provider's public URL (see note_image schema), so
# there is nothing local to mount — and mounting would fail anyway on a free
# tier with no writable disk. We therefore mount ONLY for the local backend.
if settings.image_storage_backend == "local":
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount(
        settings.media_url_prefix,
        StaticFiles(directory=settings.media_dir),
        name="media",
    )


# --- Health check -----------------------------------------------------
@app.get("/health", tags=["Health"], summary="Liveness check")
def health() -> dict[str, str]:
    """Lightweight liveness probe for load balancers / orchestrators.

    Intentionally does no database work — it answers "is the process up?",
    which is what a liveness check should test.
    """
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
