"""app/repositories/note_image_repository.py

Why this file exists:
    The repository is the ONLY layer allowed to touch the SQLAlchemy Session
    for the `note_images` table. Its single responsibility is persistence
    mechanics — add a row, list a note's images, fetch one, delete one — so
    nothing above it writes a query or manages a transaction.

    Responsibility boundary (same strict contract as NoteRepository):
        * Deals only in ORM `NoteImage` objects and primitives.
        * Knows nothing about Pydantic schemas, HTTP, or the filesystem.
        * Returns `None` for "not found" — never raises a 404. Turning
          absence into an HTTP error is the service's decision.

    How it interacts with the rest of the app:
        * Constructed with a request-scoped `Session` (from `get_db`).
        * Used by `NoteImageService`, which decides WHAT happens (and also
          drives the on-disk file); the repository decides only HOW the row
          is persisted.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.note_image import NoteImage


class NoteImageRepository:
    """Encapsulates all database access for the `note_images` table."""

    def __init__(self, session: Session) -> None:
        """Store the request-scoped session via constructor injection."""
        self._session = session

    # --- Create -------------------------------------------------------
    def create(self, image: NoteImage) -> NoteImage:
        """Persist a new image row and return it with server-generated fields.

        The service builds the `NoteImage` (after the file is on disk); the
        repository only persists it. flush/commit assign the id, refresh
        reloads server-side values (id, created_at).
        """
        self._session.add(image)
        self._session.commit()
        self._session.refresh(image)
        return image

    # --- Read ---------------------------------------------------------
    def get_by_id(self, image_id: int) -> NoteImage | None:
        """Return the image with this id, or None if it does not exist."""
        return self._session.get(NoteImage, image_id)

    def list_for_note(self, note_id: int) -> list[NoteImage]:
        """Return all images for a note, oldest-uploaded first.

        Ordering by `created_at` gives the UI a stable, predictable sequence
        (matching the `Note.images` relationship order_by).
        """
        statement = (
            select(NoteImage)
            .where(NoteImage.note_id == note_id)
            .order_by(NoteImage.created_at)
        )
        return list(self._session.execute(statement).scalars().all())

    # --- Delete -------------------------------------------------------
    def delete(self, image: NoteImage) -> None:
        """Delete an image row. The service supplies an instance it already
        fetched, so existence has been confirmed upstream. Removing the file
        on disk is the service's job — the repository only touches the DB."""
        self._session.delete(image)
        self._session.commit()
