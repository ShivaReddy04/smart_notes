"""app/services/task_service.py

Why this file exists:
    The business/use-case layer for tasks. Mirrors NoteService: it
    orchestrates each operation between the router (HTTP) and the
    repository (SQL), owns the schema<->ORM translation, and decides when
    absence becomes a 404 — all without importing FastAPI, so it stays
    reusable and unit-testable with a mocked repository.

    What differs from NoteService:
        * Instead of pinning, tasks expose `change_status`, which backs
          PATCH /tasks/{id}/status. It takes a typed `TaskStatus` and
          persists via the generic `repository.update` — the same pattern
          as pinning, just a different field.
"""

from app.models.task import Task, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.exceptions import NotFoundError


class TaskService:
    """Use-case logic for tasks."""

    def __init__(self, repository: TaskRepository, user_id: int) -> None:
        """Inject the repository (storage) and the authenticated owner.

        `user_id` scopes every read and stamps every created task, so one
        account can never see or touch another's tasks (Phase 6).
        """
        self._repository = repository
        self._user_id = user_id

    # --- Internal helper ---------------------------------------------
    def _get_or_404(self, task_id: int) -> Task:
        """Fetch the OWNER's task by id or raise NotFoundError (→ HTTP 404).

        Centralizes the existence+ownership check reused by read, update,
        status change, and delete — another user's task reads as 404.
        """
        task = self._repository.get_by_id(task_id, self._user_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        return task

    # --- Use cases ----------------------------------------------------
    def create_task(self, data: TaskCreate) -> Task:
        """Create and persist a new task from validated input.

        Maps the schema (title, description, due_date) onto ORM columns.
        `status` is omitted on purpose, so the database default ('Pending')
        applies; id and timestamps are server-owned.
        """
        task = Task(**data.model_dump(), user_id=self._user_id)
        return self._repository.create(task)

    def get_task(self, task_id: int) -> Task:
        """Return a single task, or raise NotFoundError if missing."""
        return self._get_or_404(task_id)

    def list_tasks(self, skip: int = 0, limit: int = 100) -> list[Task]:
        """Return a paginated list of the owner's tasks (newest first)."""
        return self._repository.get_all(self._user_id, skip=skip, limit=limit)

    def update_task(self, task_id: int, data: TaskUpdate) -> Task:
        """Apply a partial update (title/description/due_date) to a task.

        `exclude_unset=True` applies only the fields the client sent. Status
        is intentionally not updatable here — it has its own method.
        """
        task = self._get_or_404(task_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)
        return self._repository.update(task)

    def change_status(self, task_id: int, status: TaskStatus) -> Task:
        """Set a task's status (backs PATCH /tasks/{id}/status).

        Takes an already-validated TaskStatus (the schema enforced the
        allowed values) and persists via the generic update path. Setting
        the value explicitly keeps the operation idempotent.
        """
        task = self._get_or_404(task_id)
        task.status = status
        return self._repository.update(task)

    def delete_task(self, task_id: int) -> None:
        """Delete a task, raising NotFoundError if it does not exist."""
        task = self._get_or_404(task_id)
        self._repository.delete(task)
