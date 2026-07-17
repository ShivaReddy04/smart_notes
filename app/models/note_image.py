"""app/models/note_image.py

Why this file exists:
    Defines the persistence shape of an image attached to a note — the
    `note_images` table — as a SQLAlchemy ORM model. A note can carry many
    images (reference screenshots/photos), so this is a classic one-to-many
    child table pointing back at `notes`.

    Responsibility boundary (identical to every other model file):
      * It does NOT validate uploads (size/MIME) -> that is the storage service.
      * It does NOT run queries                   -> that is the repository.
      * It does NOT touch the filesystem          -> that is the storage service.
    The row holds ONLY metadata about an image; the image BYTES live on local
    disk under `settings.media_dir`. Keeping the two separate is what lets the
    database stay small and lets us swap storage backends later without a
    schema change.

    How it interacts with the rest of the app:
      * Inherits from `Base`, so importing this module (via app/db/base.py)
        registers the `note_images` table on `Base.metadata` for Alembic.
      * `Note.images` <-> `NoteImage.note` form the two sides of the relation.
      * The repository creates/reads/deletes instances; the response schema
        serializes them (adding the public URL built from the filename).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Imported only for type-checking to annotate the `note` relationship without
# creating a runtime circular import (note.py also references NoteImage). At
# runtime SQLAlchemy resolves the relationship by the "Note" string instead.
if TYPE_CHECKING:
    from app.models.note import Note


class NoteImage(Base):
    """ORM model mapping the `note_images` table (child of `notes`)."""

    __tablename__ = "note_images"

    # --- Identity -----------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # --- Parent link --------------------------------------------------
    # The owning note. `ondelete="CASCADE"` pushes the delete rule down to
    # PostgreSQL itself, so deleting a note removes its image rows even if it
    # happens through raw SQL or a bulk delete that bypasses the ORM. Indexed
    # because the one query we always run is "all images for this note".
    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Stored-file metadata ----------------------------------------
    # The server-generated, unique name of the file ON DISK (e.g. a random
    # hex + extension). This is what we join to `media_dir` to locate the
    # bytes and what we append to `media_url_prefix` to build the public URL.
    # It is NOT the user's filename, to avoid collisions and path-traversal.
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # The original filename as the user uploaded it. Kept purely for display
    # and download naming; never used to locate the file on disk.
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # The validated MIME type (e.g. "image/png"). Stored so the API can report
    # it and a client can render/download with the right type.
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Size of the stored file in bytes. Useful for the UI and for sanity checks.
    size: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Timestamp ----------------------------------------------------
    # Only `created_at` — an image is write-once (uploaded or deleted, never
    # edited), so TimestampMixin's `updated_at` would be meaningless here.
    # Populated by the database so it never depends on the app clock.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # --- Relationship -------------------------------------------------
    # The inverse side of `Note.images`. `back_populates` keeps both ends in
    # sync in the identity map.
    note: Mapped["Note"] = relationship(back_populates="images")

    def __repr__(self) -> str:
        """Short representation for logs; omits nothing sensitive but stays terse."""
        return (
            f"<NoteImage id={self.id!r} note_id={self.note_id!r} "
            f"filename={self.filename!r} size={self.size!r}>"
        )
