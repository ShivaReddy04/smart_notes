"""app/models/note.py

Why this file exists:
    Defines the persistence shape of a note — the `notes` table — as a
    SQLAlchemy ORM model. This is the single source of truth for *what a
    note is in the database*: its columns, types, constraints, and
    defaults.

    Responsibility boundary (kept deliberately narrow):
      * It does NOT validate user input        -> that is `schemas/note.py`.
      * It does NOT run queries                 -> that is the repository.
      * It does NOT contain business rules      -> that is the service.
    Keeping the model this thin is what preserves the Clean Architecture
    layering: the database shape can change without rippling into HTTP or
    business code, and vice versa.

    How it interacts with the rest of the app:
      * Inherits from `Base`, so importing this module registers the
        `notes` table on `Base.metadata` (which Alembic reads to generate
        migrations).
      * Repositories create/read/update/delete instances of this class.
      * Response schemas read from these instances (Pydantic
        `from_attributes`) to serialize API responses.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

# Type-only imports to annotate relationships without a runtime circular import;
# the mappers are resolved by the "NoteImage"/"User" string names.
if TYPE_CHECKING:
    from app.models.note_image import NoteImage
    from app.models.user import User


class Note(TimestampMixin, Base):
    """ORM model mapping the `notes` table.

    Uses the SQLAlchemy 2.0 typed style (`Mapped[...]` + `mapped_column`)
    so each column is statically typed and understood by editors/mypy.
    `created_at` / `updated_at` are inherited from `TimestampMixin`.
    """

    # The physical table name. Explicit and plural by convention.
    __tablename__ = "notes"

    # --- Identity -----------------------------------------------------
    # Integer surrogate primary key. Indexed for fast lookups by id, which
    # is the most common access pattern (GET /notes/{id}). Simple and
    # sufficient for Phase 1; can be swapped for a UUID later if we ever
    # need non-sequential, non-guessable public identifiers.
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # --- Ownership (Phase 6) -----------------------------------------
    # The user who owns this note. Indexed because every list/read is scoped by
    # owner. ON DELETE CASCADE removes a user's notes when the user is deleted.
    # Nullable so the column could be added to a table that already had rows
    # (those legacy notes are backfilled to the first account on registration);
    # every note created through the app sets it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # --- Core fields --------------------------------------------------
    # A note must have a title. Bounded length lets Postgres use varchar
    # and guards against unbounded input. nullable=False enforces presence
    # at the database level, not just in Pydantic.
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # The body of the note. Text = unbounded length. Optional, so a
    # title-only note is valid; stored as NULL when omitted.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Behavior flags ----------------------------------------------
    # Whether the note is pinned. Defaulted at the DATABASE level
    # (server_default) so every row — including those created by
    # migrations or manual SQL — is guaranteed a concrete value rather
    # than NULL. `func.false()` emits the SQL boolean literal.
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=func.false(),
    )

    # --- AI-derived fields (Phase 2) ---------------------------------
    # Filled automatically by the AI categorizer on create/update. Stored
    # as plain strings (not native PG enums) on purpose: the model is a
    # low-level layer and must not import the AI module's Category/Priority
    # enums, and the allowed values may evolve without an ALTER TYPE.
    # The AI layer (app/ai/schemas.py) is the source of truth and only ever
    # emits valid values, so these columns always hold legal data.
    #
    # Both are NOT NULL with server defaults that mirror NoteAnalysis
    # .fallback(), so any row created outside the AI path — a migration
    # backfill, a manual insert — is still valid. String(20) fits the
    # longest value ("Meetings").
    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Other",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Medium",
    )

    # --- Relationships -----------------------------------------------
    # The owning user (the reverse of User.notes). Optional to mirror the
    # nullable FK above.
    owner: Mapped["User | None"] = relationship(back_populates="notes")

    # Attached images (Phase 5). One note owns many NoteImage rows.
    #   * cascade="all, delete-orphan": deleting a Note (via the ORM) deletes
    #     its image rows, and removing an image from this list deletes that row.
    #   * passive_deletes=True: trust the DB's ON DELETE CASCADE to remove the
    #     children in bulk, instead of SQLAlchemy loading and deleting each one.
    #   * order_by: newest-uploaded ordering is stable and predictable for the UI.
    # NOTE: this cascades the ROWS only; the on-disk files are cleaned up by the
    # NoteImageService, since the database has no knowledge of the filesystem.
    images: Mapped[list["NoteImage"]] = relationship(
        back_populates="note",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NoteImage.created_at",
    )

    # --- Timestamps ---------------------------------------------------
    # `created_at` and `updated_at` are provided by TimestampMixin.

    def __repr__(self) -> str:
        """Developer-friendly representation for logs and debugging.

        Intentionally excludes `content` to keep log lines short and to
        avoid dumping large note bodies into logs.
        """
        return (
            f"<Note id={self.id!r} title={self.title!r} "
            f"category={self.category!r} priority={self.priority!r} "
            f"pinned={self.is_pinned!r}>"
        )
