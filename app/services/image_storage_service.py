"""app/services/image_storage_service.py

Why this file exists:
    The single place that knows how to put image BYTES on disk and take them
    off again — and the single gatekeeper that validates an upload before it
    is ever written. Isolating all filesystem contact here means:
      * the note-image service never touches `open()`/`os` directly, and
      * if storage ever moves to S3/R2, only this class changes.

    Responsibility boundary:
        * Validate size and MIME type (raising BadRequestError -> HTTP 400).
        * Generate a safe, unique, server-owned filename (NEVER derived from
          user input, so path-traversal is impossible by construction).
        * Write bytes to `media_dir`; delete bytes by stored filename.
        * It does NOT know about notes, the database, or HTTP.

    How it interacts with the rest of the app:
        * `NoteImageService` calls `save(...)` then persists the returned
          filename, and calls `delete(...)` when an image row is removed.
        * `get_image_storage_service()` builds a cached singleton from
          Settings, so the media directory is ensured to exist exactly once.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.utils.exceptions import BadRequestError

logger = logging.getLogger("ai_smart_notes")

# Map each accepted MIME type to the extension we store it under. The stored
# name's extension is chosen from THIS map (never from the user's filename),
# so a mislabeled or hostile original name cannot influence the path.
_EXTENSION_BY_TYPE: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class ImageStorageService:
    """Validates uploads and stores their bytes on local disk."""

    def __init__(
        self,
        media_dir: str,
        allowed_types: list[str],
        max_bytes: int,
    ) -> None:
        """Inject the storage policy (dir, allowed types, size cap) so the
        class is testable with a temp directory and small limits.

        The media directory is created up front (parents included) so the
        first upload never fails on a missing folder.
        """
        self._dir = Path(media_dir)
        self._allowed_types = set(allowed_types)
        self._max_bytes = max_bytes
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, content_type: str, original_name: str) -> str:
        """Validate and write an uploaded image; return its stored filename.

        Validation order (fail before touching disk):
          1. Non-empty.
          2. MIME type is in the whitelist.
          3. Size within the configured cap.
        The stored name is `<random hex><ext>`, unique by construction, so
        two uploads of the same original file never collide.
        """
        if not data:
            raise BadRequestError("Uploaded image is empty.")

        if content_type not in self._allowed_types:
            allowed = ", ".join(sorted(self._allowed_types))
            raise BadRequestError(
                f"Unsupported image type '{content_type}'. Allowed: {allowed}."
            )

        if len(data) > self._max_bytes:
            max_mb = self._max_bytes / (1024 * 1024)
            raise BadRequestError(
                f"Image is too large ({len(data)} bytes); max is {max_mb:.1f} MB."
            )

        extension = _EXTENSION_BY_TYPE[content_type]
        filename = f"{secrets.token_hex(16)}{extension}"
        destination = self._dir / filename
        destination.write_bytes(data)
        logger.info(
            "Stored image %s (%d bytes, %s) from original %r",
            filename,
            len(data),
            content_type,
            original_name,
        )
        return filename

    def delete(self, filename: str) -> None:
        """Delete a stored file by its filename. Best-effort and idempotent.

        A missing file is NOT an error: if the row exists but the file was
        already removed, the desired end state (no file) is met. We never let
        a filesystem hiccup block the row deletion above us, so we log and
        swallow unexpected errors.
        """
        try:
            (self._dir / filename).unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete image file %s", filename)


@lru_cache
def get_image_storage_service() -> ImageStorageService:
    """Return a cached ImageStorageService built from Settings.

    Cached so the media directory is created once and the same instance is
    reused across requests (there is no per-request state).
    """
    settings = get_settings()
    return ImageStorageService(
        media_dir=settings.media_dir,
        allowed_types=settings.allowed_image_types,
        max_bytes=settings.max_image_bytes,
    )
