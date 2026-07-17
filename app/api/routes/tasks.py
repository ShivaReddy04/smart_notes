"""app/api/routes/tasks.py

Why this file exists:
    The HTTP boundary for tasks. Mirrors the notes router: each endpoint
    only translates a request into a service call and shapes the response —
    no business logic, no SQL. It also owns the task dependency wiring
    (`get_task_service`: get_db -> TaskRepository -> TaskService).

    What differs from the notes router:
        * Instead of a pin endpoint, there is PATCH /tasks/{id}/status,
          which takes a `TaskStatusUpdate` body (a validated enum value) and
          calls `service.change_status`.

    How it interacts with the rest of the app:
        * `main.py` includes this router under the global API prefix.
        * FastAPI validates bodies against the task schemas and serializes
          responses via `response_model=TaskResponse`.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskResponse, TaskStatusUpdate, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_task_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskService:
    """Assemble a request-scoped, user-scoped TaskService.

    Resolves the DB session and authenticates the bearer token, so every tasks
    route requires a valid login (401 without one) and is bound to the owner.
    NOTE: the chat route reuses this dependency, so chat's task context is
    automatically scoped to the current user too.
    """
    return TaskService(TaskRepository(db), user_id=current_user.id)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Create a new task (starts as 'Pending'). Returns the created task."""
    return service.create_task(payload)


@router.get(
    "",
    response_model=list[TaskResponse],
    summary="List tasks",
)
def list_tasks(
    skip: int = Query(0, ge=0, description="Number of tasks to skip."),
    limit: int = Query(100, ge=1, le=500, description="Max tasks to return."),
    service: TaskService = Depends(get_task_service),
) -> list[TaskResponse]:
    """Return a paginated list of tasks (newest first)."""
    return service.list_tasks(skip=skip, limit=limit)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a single task",
)
def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Return one task by id, or 404 if it does not exist."""
    return service.get_task(task_id)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Apply a partial update to a task. Only provided fields change.
    Status is changed via the dedicated status endpoint, not here."""
    return service.update_task(task_id, payload)


@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="Change a task's status",
)
def change_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Set a task's status to one of Pending / In Progress / Completed."""
    return service.change_status(task_id, payload.status)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> None:
    """Delete a task by id (404 if missing). Returns no content on success."""
    service.delete_task(task_id)
