"""app/services/image_storage_service.py

Why this file exists:
    The single place that knows how to put image BYTES into storage and take
    them off again — and the single gatekeeper that validates an upload before
    it is ever written. Isolating all storage contact here means the note-image
    service never touches `open()`/boto3 directly, and swapping backends is a
    change confined to this file.

    Two backends, one interface:
        * LocalImageStorage -> bytes on local disk under `media_dir`, served by
          StaticFiles. Used in development.
        * S3ImageStorage    -> bytes in any S3-compatible object storage via
          boto3 (Supabase Storage, Cloudflare R2, AWS S3, MinIO). Used in
          production, because the free tier has no persistent disk. Objects are
          read publicly straight from the provider's CDN; the API never proxies
          image bytes.
    `get_image_storage_service()` picks the backend from Settings, so callers
    just depend on the abstract ImageStorageService.

    Responsibility boundary:
        * Validate size and MIME type (raising BadRequestError -> HTTP 400).
        * Generate a safe, unique, server-owned filename (NEVER derived from
          user input, so path-traversal is impossible by construction).
        * Persist bytes; delete bytes by stored filename.
        * It does NOT know about notes, the database, HTTP, or how the public
          URL is built (that is the note_image schema).

    How it interacts with the rest of the app:
        * `NoteImageService` calls `save(...)` then persists the returned
          filename, and calls `delete(...)` when an image row is removed.
"""

from __future__ import annotations

import logging
import secrets
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.utils.exceptions import BadRequestError

logger = logging.getLogger("ai_smart_notes")

# Map each accepted MIME type to the extension we store it under. The stored
# name's extension is chosen from THIS map (never from the user's filename),
# so a mislabeled or hostile original name cannot influence the key/path.
_EXTENSION_BY_TYPE: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class ImageStorageService(ABC):
    """Validates uploads and stores their bytes in some backend.

    The validation, size cap, and safe-name generation are shared here; each
    concrete backend implements only where the bytes actually go (`_write`) and
    how they are removed (`delete`).
    """

    def __init__(self, allowed_types: list[str], max_bytes: int) -> None:
        self._allowed_types = set(allowed_types)
        self._max_bytes = max_bytes

    def save(self, data: bytes, content_type: str, original_name: str) -> str:
        """Validate and store an uploaded image; return its stored filename.

        Validation order (fail before touching storage):
          1. Non-empty.
          2. MIME type is in the whitelist.
          3. Size within the configured cap.
        The stored name is `<random hex><ext>`, unique by construction, so two
        uploads of the same original file never collide.
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

        filename = f"{secrets.token_hex(16)}{_EXTENSION_BY_TYPE[content_type]}"
        self._write(data, filename, content_type)
        logger.info(
            "Stored image %s (%d bytes, %s) from original %r",
            filename,
            len(data),
            content_type,
            original_name,
        )
        return filename

    @abstractmethod
    def _write(self, data: bytes, filename: str, content_type: str) -> None:
        """Persist already-validated bytes under `filename` in the backend."""

    @abstractmethod
    def delete(self, filename: str) -> None:
        """Delete a stored object by its filename. Best-effort and idempotent."""


class LocalImageStorage(ImageStorageService):
    """Stores image bytes on the local filesystem (development backend)."""

    def __init__(self, media_dir: str, allowed_types: list[str], max_bytes: int) -> None:
        """The media directory is created up front (parents included) so the
        first upload never fails on a missing folder."""
        super().__init__(allowed_types, max_bytes)
        self._dir = Path(media_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _write(self, data: bytes, filename: str, content_type: str) -> None:
        (self._dir / filename).write_bytes(data)

    def delete(self, filename: str) -> None:
        """Delete a file by name. A missing file is NOT an error: the desired
        end state (no file) is already met. Never let a filesystem hiccup block
        the row deletion above us, so log and swallow unexpected errors."""
        try:
            (self._dir / filename).unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete image file %s", filename)


class S3ImageStorage(ImageStorageService):
    """Stores image bytes in any S3-compatible object storage via boto3.

    Works with Supabase Storage, Cloudflare R2, AWS S3, MinIO — they all speak
    the S3 API, so a standard boto3 S3 client works once pointed at the
    provider's endpoint + region. The client is built once and reused. Public
    reads happen directly against the bucket's public URL (built by the schema),
    so this class only ever writes and deletes.
    """

    def __init__(
        self,
        endpoint_url: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        allowed_types: list[str],
        max_bytes: int,
    ) -> None:
        super().__init__(allowed_types, max_bytes)
        # Imported lazily so the (heavier) boto3 import is only paid when the S3
        # backend is actually selected, keeping local/dev startup light.
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # Supabase/AWS validate the region; R2 ignores it but the S3 client
            # still requires a value (use "auto" for R2).
            region_name=region,
        )

    def _write(self, data: bytes, filename: str, content_type: str) -> None:
        # ContentType is set so the browser renders the object inline (image/*)
        # instead of downloading it as octet-stream.
        self._client.put_object(
            Bucket=self._bucket,
            Key=filename,
            Body=data,
            ContentType=content_type,
        )

    def delete(self, filename: str) -> None:
        """Delete an object by key. S3 delete is already idempotent (a missing
        key is not an error), but we still log+swallow any transport error so a
        storage hiccup cannot block the row deletion above us."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=filename)
        except Exception:  # noqa: BLE001 — best-effort, mirrors the local backend
            logger.exception("Failed to delete S3 object %s", filename)


@lru_cache
def get_image_storage_service() -> ImageStorageService:
    """Return a cached ImageStorageService chosen from Settings.

    Cached so the backend (and, for S3, its boto3 client / for local, its
    directory) is built once and reused across requests. The backend is
    selected by `image_storage_backend`: "s3" in production, "local" otherwise.
    """
    settings = get_settings()
    if settings.image_storage_backend == "s3":
        logger.info("Using S3 image storage (bucket=%s)", settings.s3_bucket)
        return S3ImageStorage(
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            bucket=settings.s3_bucket,
            allowed_types=settings.allowed_image_types,
            max_bytes=settings.max_image_bytes,
        )
    logger.info("Using local-disk image storage (dir=%s)", settings.media_dir)
    return LocalImageStorage(
        media_dir=settings.media_dir,
        allowed_types=settings.allowed_image_types,
        max_bytes=settings.max_image_bytes,
    )
