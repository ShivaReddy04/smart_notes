"""app/services/note_image_service.py

Why this file exists:
    The use-case layer for attaching images to notes. It coordinates the two
    collaborators that each own half the job — the storage service (bytes on
    disk) and the image repository (metadata row) — and enforces the rules
    that span both: the note must exist, an image belongs to exactly one
    note, and the on-disk file and the DB row must not drift apart.

    Responsibility boundary:
        * Decides WHAT happens and WHEN absence becomes a 404 (raises domain
          errors from utils.exceptions). Never imports FastAPI.
        * Keeps the file and the row consistent: if the row insert fails
          after the file is written, it deletes the orphaned file; when a row
          is deleted, it deletes the file too.

    How it interacts with the rest of the app:
        * Constructed with a NoteRepository (existence checks), a
          NoteImageRepository (row persistence) and an ImageStorageService
          (disk I/O) — all injected, so it is unit-testable with fakes.
        * Called by the note-images router; returns ORM `NoteImage` objects
          which the router serializes via `response_model=NoteImageResponse`.
"""

import logging

from app.models.note_image import NoteImage
from app.repositories.note_image_repository import NoteImageRepository
from app.repositories.note_repository import NoteRepository
from app.services.image_storage_service import ImageStorageService
from app.utils.exceptions import NotFoundError

logger = logging.getLogger("ai_smart_notes")


class NoteImageService:
    """Use-case logic for a note's attached images."""

    def __init__(
        self,
        note_repository: NoteRepository,
        image_repository: NoteImageRepository,
        storage: ImageStorageService,
        user_id: int,
    ) -> None:
        """Inject collaborators:
          * `note_repository`  -> confirm the parent note exists.
          * `image_repository` -> persist/list/delete image ROWS.
          * `storage`          -> write/delete image BYTES on disk.
          * `user_id`          -> the authenticated owner; the parent-note check
            is scoped to it, so a user can only attach to / read images of their
            OWN notes (Phase 6).
        """
        self._notes = note_repository
        self._images = image_repository
        self._storage = storage
        self._user_id = user_id

    # --- Internal helper ---------------------------------------------
    def _ensure_note_exists(self, note_id: int) -> None:
        """Raise NotFoundError (→ 404) if the note is missing OR not owned.

        Images are meaningless without their note, so every operation starts by
        confirming the note exists AND belongs to the current user — another
        user's note reads as 404, never revealing it. Same rule the note service
        applies, enforced here at the image boundary.
        """
        if self._notes.get_by_id(note_id, self._user_id) is None:
            raise NotFoundError("Note", note_id)

    # --- Use cases ----------------------------------------------------
    def add_image(
        self,
        note_id: int,
        data: bytes,
        content_type: str,
        original_name: str,
    ) -> NoteImage:
        """Attach an uploaded image to a note.

        Order matters for consistency: verify the note, validate+write the
        file, THEN insert the row. If the row insert fails, the just-written
        file would be orphaned, so we delete it before re-raising — leaving
        no file without a matching row.
        """
        self._ensure_note_exists(note_id)

        # Validates type/size and writes bytes; raises BadRequestError on
        # invalid input before anything is persisted.
        filename = self._storage.save(data, content_type, original_name)

        image = NoteImage(
            note_id=note_id,
            filename=filename,
            original_name=original_name,
            content_type=content_type,
            size=len(data),
        )
        try:
            return self._images.create(image)
        except Exception:
            # Roll back the side effect on disk so a failed insert cannot
            # leave an orphaned file behind, then let the error propagate to
            # the global handler (→ 500).
            logger.exception(
                "Failed to persist image row for note %s; removing orphaned file %s",
                note_id,
                filename,
            )
            self._storage.delete(filename)
            raise

    def list_images(self, note_id: int) -> list[NoteImage]:
        """Return all images attached to a note (404 if the note is missing)."""
        self._ensure_note_exists(note_id)
        return self._images.list_for_note(note_id)

    def delete_image(self, note_id: int, image_id: int) -> None:
        """Remove one image from a note: its row AND its file.

        Guards that the image exists and truly belongs to THIS note (so a
        mismatched note_id/image_id pair is a 404, not a cross-note delete).
        The row is deleted first; the file is then removed best-effort, so a
        filesystem error cannot resurrect an already-deleted row.
        """
        image = self._images.get_by_id(image_id)
        if image is None or image.note_id != note_id:
            raise NotFoundError("Image", image_id)

        filename = image.filename
        self._images.delete(image)
        self._storage.delete(filename)
