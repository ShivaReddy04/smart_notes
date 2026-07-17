"""app/repositories/task_repository.py

Why this file exists:
    The single owner of all SQL for the `tasks` table. Mirrors
    NoteRepository: it is the only place that touches the Session for
    tasks, deals exclusively in ORM `Task` objects and primitives, and
    returns `None` for "not found" rather than raising an HTTP error (the
    service makes the 404 decision).

    What differs from the note repository:
        * Tasks have no "pinned" concept, so listing simply orders by
          newest first (`created_at` descending).
        * Status changes are NOT a special method — they reuse the generic
          `update()`, exactly like a field edit (Open/Closed: no method
          explosion as new mutations appear).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task


class TaskRepository:
    """Encapsulates all database access for the `tasks` table."""

    def __init__(self, session: Session) -> None:
        """Store the request-scoped session via constructor injection."""
        self._session = session

    # --- Create -------------------------------------------------------
    def create(self, task: Task) -> Task:
        """Persist a new task and return it with server-generated fields
        (id, status default, timestamps) loaded."""
        self._session.add(task)
        self._session.commit()
        self._session.refresh(task)
        return task

    # --- Read ---------------------------------------------------------
    def get_by_id(self, task_id: int) -> Task | None:
        """Return the task with this id, or None if it does not exist."""
        return self._session.get(Task, task_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Task]:
        """Return a page of tasks, newest first, with offset pagination."""
        statement = (
            select(Task)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    # --- Update -------------------------------------------------------
    def update(self, task: Task) -> Task:
        """Persist changes to an already-mutated, session-attached task.

        Serves every mutation — editing fields AND changing status — so the
        status endpoint needs no dedicated persistence method.
        """
        self._session.commit()
        self._session.refresh(task)
        return task

    # --- Delete -------------------------------------------------------
    def delete(self, task: Task) -> None:
        """Delete a task the service has already fetched (existence
        confirmed upstream)."""
        self._session.delete(task)
        self._session.commit()
