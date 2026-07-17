"""app/services/note_service.py

Why this file exists:
    The business/use-case layer for notes. It orchestrates the steps of
    each operation — validate intent, fetch, mutate, persist — sitting
    between the routers (HTTP) and the repository (SQL). This is the layer
    that owns application logic, and the exact seam where Phase 2's AI
    categorization will later plug in without touching HTTP or DB code.

    Responsibility boundary:
        * Translates validated schemas into ORM objects and back-intent.
        * Decides WHAT changes and WHEN absence becomes a 404 (by raising
          domain errors from `utils.exceptions`).
        * Depends only on the repository abstraction and the schemas —
          never on FastAPI. That keeps it reusable (CLI, worker, tests) and
          unit-testable with a mocked repository.

    How it interacts with the rest of the app:
        * Constructed with a `NoteRepository` (dependency injection).
        * Called by the notes router; returns ORM `Note` objects which the
          router serializes via `response_model=NoteResponse`.
"""

from app.ai.categorizer import NoteCategorizer
from app.ai.task_extractor import TaskExtractor
from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.task import TaskSuggestion
from app.services.note_embedding_service import NoteEmbeddingService
from app.utils.exceptions import NotFoundError


class NoteService:
    """Use-case logic for notes."""

    def __init__(
        self,
        repository: NoteRepository,
        categorizer: NoteCategorizer,
        note_embedding_service: NoteEmbeddingService,
        task_extractor: TaskExtractor,
        user_id: int,
    ) -> None:
        """Inject collaborators so the service is decoupled from concrete
        implementations and testable with fakes:
          * `repository`             -> how notes are stored.
          * `categorizer`            -> how a note's category/priority are derived.
          * `note_embedding_service` -> best-effort sync of the note into the
            vector index. It never raises, so semantic-search indexing can
            never break a CRUD operation (Feature 7).
          * `task_extractor`         -> suggests to-do tasks from a note's text.
          * `user_id`                -> the authenticated owner. Every read is
            scoped to it and every created note is stamped with it, so one
            account can never see or touch another's notes (Phase 6).
        """
        self._repository = repository
        self._categorizer = categorizer
        self._note_embedding_service = note_embedding_service
        self._task_extractor = task_extractor
        self._user_id = user_id

    # --- AI helpers ---------------------------------------------------
    @staticmethod
    def _compose_text(title: str, content: str | None) -> str:
        """Build the text handed to the AI from a note's title and body.

        Both fields carry signal, so we join the non-empty parts. (Empty
        input is handled safely by the categorizer, which returns the
        fallback without calling the LLM.)
        """
        parts = [part for part in (title, content) if part]
        return "\n\n".join(parts)

    def _apply_analysis(self, note: Note) -> None:
        """Run AI analysis on a note's current text and set its category and
        priority. Centralized so create and update share one path.

        `analyze()` never raises — on any failure it returns the safe
        fallback (Other/Medium) — so no error handling is needed here. We
        store the human-readable enum values ('Coding', 'High') as strings.
        """
        analysis = self._categorizer.analyze(self._compose_text(note.title, note.content))
        note.category = analysis.category.value
        note.priority = analysis.priority.value

    # --- Internal helper ---------------------------------------------
    def _get_or_404(self, note_id: int) -> Note:
        """Fetch a note by id or raise NotFoundError (→ HTTP 404).

        Centralizes the "exists?" check so the 404 rule is written once and
        reused by read, update, pin, and delete.
        """
        note = self._repository.get_by_id(note_id, self._user_id)
        if note is None:
            raise NotFoundError("Note", note_id)
        return note

    # --- Use cases ----------------------------------------------------
    def create_note(self, data: NoteCreate) -> Note:
        """Create and persist a new note from validated input.

        Workflow (Feature 6): build the note from the user's text, run AI
        analysis to derive category + priority, then persist everything and
        return the complete note. Server-owned fields (id, is_pinned,
        timestamps) are filled by the database.
        """
        note = Note(**data.model_dump(), user_id=self._user_id)
        self._apply_analysis(note)
        created = self._repository.create(note)
        # Best-effort: index the persisted note (it now has id + timestamps) for
        # semantic search. sync_note never raises, so a vector/Chroma failure
        # cannot break note creation.
        self._note_embedding_service.sync_note(created)
        return created

    def get_note(self, note_id: int) -> Note:
        """Return a single note, or raise NotFoundError if it is missing."""
        return self._get_or_404(note_id)

    def list_notes(self, skip: int = 0, limit: int = 100) -> list[Note]:
        """Return a paginated list of the owner's notes (pinned first, newest)."""
        return self._repository.get_all(self._user_id, skip=skip, limit=limit)

    def update_note(self, note_id: int, data: NoteUpdate) -> Note:
        """Apply a partial update to an existing note.

        `exclude_unset=True` yields ONLY the fields the client actually
        sent, so omitted fields are left unchanged. We mutate the fetched
        (session-attached) instance and let the repository persist it.
        """
        note = self._get_or_404(note_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(note, field, value)
        # Re-derive category/priority only when the text actually changed,
        # so a no-op update does not pay for an LLM call.
        if "title" in changes or "content" in changes:
            self._apply_analysis(note)
        updated = self._repository.update(note)
        # Re-index so the vector's metadata (and its embedding, if the text
        # changed) stays consistent with the persisted note. Best-effort; the
        # upsert is keyed on the note id, so this overwrites the old vector.
        self._note_embedding_service.sync_note(updated)
        return updated

    def set_pin(self, note_id: int, pinned: bool) -> Note:
        """Pin or unpin a note (backs PATCH /notes/{id}/pin).

        The pin intent lives here in the service; the repository stays a
        generic persister. Setting the value explicitly (rather than
        toggling) makes the operation idempotent — pinning an already
        pinned note is a no-op.
        """
        note = self._get_or_404(note_id)
        note.is_pinned = pinned
        return self._repository.update(note)

    def delete_note(self, note_id: int) -> None:
        """Delete a note, raising NotFoundError if it does not exist."""
        note = self._get_or_404(note_id)
        self._repository.delete(note)
        # Best-effort: drop the note's vector from the index. remove_note never
        # raises, so a vector-store failure cannot block the deletion.
        self._note_embedding_service.remove_note(note_id)

    def suggest_tasks(self, note_id: int) -> list[TaskSuggestion]:
        """Return AI-suggested to-do tasks drawn from the note's text.

        Fetches the OWNER's note (404 if missing or not theirs), then runs the
        extractor over its title + content. The suggestions are DRAFTS only —
        nothing is persisted here; the client turns the chosen ones into real
        tasks via the normal create-task endpoint. Extraction is best-effort:
        an empty list means "no actionable items" (or a transient AI hiccup),
        never an error.
        """
        note = self._get_or_404(note_id)
        return self._task_extractor.extract(self._compose_text(note.title, note.content))
