"""app/repositories/note_repository.py

Why this file exists:
    The repository is the ONLY layer allowed to touch the SQLAlchemy
    Session. Its single responsibility is the persistence mechanics for
    notes — add, fetch, list, persist changes, delete — so that no layer
    above it ever writes a query or manages a transaction.

    Responsibility boundary (deliberately strict):
        * Deals only in ORM `Note` objects and primitives.
        * Knows nothing about Pydantic schemas or HTTP.
        * Returns `None` for "not found" — it never raises a 404. Turning
          absence into an HTTP error is a decision for the service layer.
        This isolation is what makes services unit-testable (mock the
        repository) and keeps SQL in exactly one place.

    How it interacts with the rest of the app:
        * Constructed with a request-scoped `Session` (from `get_db`).
        * Used by `NoteService`, which decides WHAT changes; the repository
          decides only HOW it is persisted.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.note import Note


class NoteRepository:
    """Encapsulates all database access for the `notes` table."""

    def __init__(self, session: Session) -> None:
        """Store the request-scoped session via constructor injection.

        Injecting the session (rather than reaching for a global) makes the
        dependency explicit and lets tests pass a throwaway/in-memory
        session.
        """
        self._session = session

    # --- Create -------------------------------------------------------
    def create(self, note: Note) -> Note:
        """Persist a new note and return it with server-generated fields.

        The service builds the `Note` instance (mapping the validated
        schema); the repository only persists it. `flush` sends the INSERT
        so the DB assigns the id, `commit` finalizes the transaction, and
        `refresh` reloads server-side values (id, timestamps, is_pinned).
        """
        self._session.add(note)
        self._session.commit()
        self._session.refresh(note)
        return note

    # --- Read ---------------------------------------------------------
    def get_by_id(self, note_id: int, user_id: int) -> Note | None:
        """Return the note with this id IF it belongs to `user_id`, else None.

        Scoping the lookup by owner is what enforces isolation: another user's
        note (or a non-existent id) both read as None here, so upstream it
        becomes a 404 that never reveals whether the note exists. Returning
        None — not raising — keeps the 404 decision in the service.
        """
        statement = select(Note).where(Note.id == note_id, Note.user_id == user_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_all(self, user_id: int, skip: int = 0, limit: int = 100) -> list[Note]:
        """Return a page of the OWNER's notes, pinned first then newest first.

        The `user_id` filter scopes the list to one account. Ordering by
        `is_pinned` descending surfaces pinned notes at the top; `created_at`
        descending shows the most recent first within each group.
        `skip`/`limit` provide simple offset pagination for the list endpoint.
        """
        statement = (
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.is_pinned.desc(), Note.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        # `.scalars()` unwraps single-entity rows into Note objects;
        # `list(...)` materializes the Sequence into a concrete list.
        return list(self._session.execute(statement).scalars().all())

    # --- Update -------------------------------------------------------
    def update(self, note: Note) -> Note:
        """Persist changes to an already-mutated, session-attached note.

        The service fetches the note (via get_by_id, same session), mutates
        the desired attributes, then calls this to commit. This single
        method serves every mutation — editing fields, pinning/unpinning —
        so there is no bespoke method per field (Open/Closed).
        """
        self._session.commit()
        self._session.refresh(note)
        return note

    # --- Delete -------------------------------------------------------
    def delete(self, note: Note) -> None:
        """Delete a note. The service supplies an instance it already
        fetched, so existence has already been confirmed upstream."""
        self._session.delete(note)
        self._session.commit()
