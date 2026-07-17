"""app/api/routes/notes.py

Why this file exists:
    The HTTP boundary for notes. Each endpoint's only job is translation:
    take a URL + method + validated body, call the matching service method,
    and return the result with the correct status code. There is NO
    business logic and NO SQL here — both live below this layer.

    This module also owns the dependency wiring for notes: `get_note_service`
    assembles the per-request chain get_db -> NoteRepository -> NoteService
    using FastAPI's `Depends`, so endpoints simply declare the service they
    need and stay decoupled from how it is constructed.

    How it interacts with the rest of the app:
        * `main.py` includes this router under the global API prefix.
        * Endpoints depend on `NoteService`; FastAPI validates request
          bodies against the note schemas and serializes responses via
          `response_model=NoteResponse`.
"""

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.ai.categorizer import get_categorizer
from app.core.database import get_db
from app.repositories.note_repository import NoteRepository
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.services.note_embedding_service import get_note_embedding_service
from app.services.note_service import NoteService

# `prefix` groups every route under /notes; `tags` groups them in the docs.
# The global /api/v1 prefix is applied once when main.py includes us.
router = APIRouter(prefix="/notes", tags=["Notes"])


def get_note_service(db: Session = Depends(get_db)) -> NoteService:
    """Assemble a request-scoped NoteService.

    FastAPI resolves `get_db` (yielding a session for this request), then we
    layer the repository and service on top. The categorizer and the note
    embedding service are cached singletons (their LLM client / embedding
    model / Chroma client are reused across requests). Declaring this as a
    dependency keeps construction in one place and lets tests override it.
    """
    return NoteService(
        NoteRepository(db),
        get_categorizer(),
        get_note_embedding_service(),
    )


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
)
def create_note(
    payload: NoteCreate,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Create a new note. Returns the created note with id and timestamps."""
    return service.create_note(payload)


@router.get(
    "",
    response_model=list[NoteResponse],
    summary="List notes",
)
def list_notes(
    skip: int = Query(0, ge=0, description="Number of notes to skip."),
    limit: int = Query(100, ge=1, le=500, description="Max notes to return."),
    service: NoteService = Depends(get_note_service),
) -> list[NoteResponse]:
    """Return a paginated list of notes (pinned first, then newest)."""
    return service.list_notes(skip=skip, limit=limit)


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a single note",
)
def get_note(
    note_id: int,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Return one note by id, or 404 if it does not exist."""
    return service.get_note(note_id)


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update a note",
)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Apply a partial update to a note. Only provided fields change."""
    return service.update_note(note_id, payload)


@router.patch(
    "/{note_id}/pin",
    response_model=NoteResponse,
    summary="Pin or unpin a note",
)
def set_note_pin(
    note_id: int,
    pinned: bool = Body(..., embed=True, description="True to pin, False to unpin."),
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Set a note's pinned state. Request body: {"pinned": true|false}."""
    return service.set_pin(note_id, pinned)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
)
def delete_note(
    note_id: int,
    service: NoteService = Depends(get_note_service),
) -> None:
    """Delete a note by id (404 if missing). Returns no content on success."""
    service.delete_note(note_id)
