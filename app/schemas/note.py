"""app/schemas/note.py

Why this file exists:
    Defines the API contract for notes — the Pydantic models that validate
    incoming request JSON and serialize outgoing response JSON. This is the
    translation boundary between the HTTP world and the domain.

    Responsibility boundary:
        Shape + validation of data crossing the API only. It knows nothing
        about how notes are stored (that is the ORM model) or how they are
        fetched (that is the repository). Keeping the wire shape separate
        from the database shape lets each evolve independently and ensures
        clients can never set server-owned fields (id, timestamps).

    How it interacts with the rest of the app:
        * Routers declare these as request bodies / response_model, so
          FastAPI validates input and documents the schema automatically.
        * Services receive validated `NoteCreate` / `NoteUpdate` objects.
        * `NoteResponse` is built directly from an ORM `Note` instance via
          `from_attributes=True`, turning a database row into JSON.

    The three-schema split (Create / Update / Response) exists because each
    direction has a different contract:
        * what a client MAY send when creating,
        * what a client MAY change when updating (all optional),
        * what the server ALWAYS returns (including read-only fields).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# The canonical sets of valid AI-derived values. Imported here because the
# response schema is the API contract for these fields; the AI layer is
# their single source of truth (mirrors TaskResponse using TaskStatus).
from app.ai.schemas import Category, Priority

# Attached images (Phase 5). NoteResponse embeds a list of these so a note and
# its images travel together in a single payload.
from app.schemas.note_image import NoteImageResponse


class NoteBase(BaseModel):
    """Fields a client may provide, shared by create (and reused as the
    basis for the response).

    `str_strip_whitespace=True` trims leading/trailing whitespace before
    validation, so a title of "   " becomes "" and then fails the
    `min_length=1` check rather than slipping through as blank.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # Required. Bounds mirror the DB column (String(255), NOT NULL) so the
    # API rejects invalid input before it ever reaches the database.
    title: str = Field(
        min_length=1,
        max_length=255,
        description="Short title of the note.",
        examples=["Groceries"],
    )

    # Optional free-form body. `None` means "no content".
    content: str | None = Field(
        default=None,
        description="Optional body text of the note.",
        examples=["Milk, eggs, bread"],
    )


class NoteCreate(NoteBase):
    """Request body for POST /notes.

    Inherits exactly the client-settable fields from NoteBase. Note that
    `is_pinned`, `id`, and timestamps are intentionally absent: a new note
    is never pinned via create (use the dedicated pin endpoint), and the
    server owns identity and timestamps.
    """


class NoteUpdate(BaseModel):
    """Request body for PUT /notes/{id}.

    Every field is OPTIONAL so the client can send a partial update —
    only the provided fields are changed. The service distinguishes
    "field omitted" from "field set to null" using
    `model_dump(exclude_unset=True)`.

    `is_pinned` is deliberately NOT here: pin state is changed only through
    PATCH /notes/{id}/pin, giving exactly one way to toggle it.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New title, if changing it.",
    )
    content: str | None = Field(
        default=None,
        description="New body text, if changing it.",
    )


class NoteResponse(NoteBase):
    """Response body returned for every note-returning endpoint.

    Extends the client fields with the server-owned, read-only fields.
    `from_attributes=True` lets FastAPI/Pydantic build this directly from a
    SQLAlchemy `Note` ORM instance by reading its attributes, e.g.
    `NoteResponse.model_validate(note)`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Server-assigned unique identifier.")
    is_pinned: bool = Field(description="Whether the note is pinned.")

    # AI-derived, read-only. Present only on the response (never on create/
    # update), so clients cannot set them — the category/priority are chosen
    # automatically by the AI categorizer.
    category: Category = Field(description="AI-assigned category of the note.")
    priority: Priority = Field(description="AI-assigned priority of the note.")

    created_at: datetime = Field(description="When the note was created (UTC-aware).")
    updated_at: datetime = Field(description="When the note was last updated (UTC-aware).")

    # Attached images, newest-ordered by the relationship. Populated from the
    # ORM `Note.images` relationship via from_attributes; defaults to an empty
    # list so a note with no images still serializes cleanly.
    images: list[NoteImageResponse] = Field(
        default_factory=list,
        description="Images attached to this note.",
    )
