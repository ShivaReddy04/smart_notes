"""app/api/routes/note_images.py

Why this file exists:
    The HTTP boundary for a note's images. Each endpoint only translates:
    take the URL + uploaded file, call the matching service method, and
    return the result with the right status code. No business logic, no SQL,
    no filesystem access here — those live below this layer.

    These routes are nested under a note (`/notes/{note_id}/images`) because
    an image never exists on its own; it always belongs to exactly one note.

    This module also owns the dependency wiring for image use-cases:
    `get_note_image_service` assembles the per-request chain
    get_db -> repositories -> NoteImageService, plus the cached storage
    singleton, so endpoints simply declare the service they need.

    How it interacts with the rest of the app:
        * `main.py` includes this router under the global API prefix, and
          separately mounts the media directory as static files so the
          stored images are actually fetchable at their `url`.
"""

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.note_image_repository import NoteImageRepository
from app.repositories.note_repository import NoteRepository
from app.schemas.note_image import NoteImageResponse
from app.services.image_storage_service import get_image_storage_service
from app.services.note_image_service import NoteImageService

# Nested under a note; the global /api/v1 prefix is applied by main.py.
router = APIRouter(prefix="/notes/{note_id}/images", tags=["Note images"])


def get_note_image_service(db: Session = Depends(get_db)) -> NoteImageService:
    """Assemble a request-scoped NoteImageService.

    FastAPI resolves `get_db` (a session for this request); we layer the two
    repositories on top and inject the cached storage singleton (its media
    directory is created once). Centralizing construction here keeps the
    endpoints thin and lets tests override the dependency.
    """
    return NoteImageService(
        NoteRepository(db),
        NoteImageRepository(db),
        get_image_storage_service(),
    )


@router.post(
    "",
    response_model=NoteImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach an image to a note",
)
def upload_image(
    note_id: int,
    file: UploadFile,
    service: NoteImageService = Depends(get_note_image_service),
) -> NoteImageResponse:
    """Upload one image (multipart/form-data field `file`) and attach it.

    The bytes are read synchronously from the SpooledTemporaryFile — this is
    a sync endpoint, so it runs in FastAPI's threadpool and does not block
    the event loop. Validation (type/size) and the 404-if-note-missing rule
    live in the service; a bad upload returns 400, a missing note 404.
    """
    data = file.file.read()
    return service.add_image(
        note_id,
        data,
        file.content_type or "application/octet-stream",
        file.filename or "upload",
    )


@router.get(
    "",
    response_model=list[NoteImageResponse],
    summary="List a note's images",
)
def list_images(
    note_id: int,
    service: NoteImageService = Depends(get_note_image_service),
) -> list[NoteImageResponse]:
    """Return every image attached to the note (404 if the note is missing)."""
    return service.list_images(note_id)


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an image from a note",
)
def delete_image(
    note_id: int,
    image_id: int,
    service: NoteImageService = Depends(get_note_image_service),
) -> None:
    """Delete one image (row + file). 404 if it doesn't belong to this note."""
    service.delete_image(note_id, image_id)
