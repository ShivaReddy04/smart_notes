"""app/schemas/task.py

Why this file exists:
    Defines the API contract for tasks — the Pydantic models that validate
    incoming request JSON and serialize outgoing response JSON. Same role
    and boundary as the note schemas: shape + validation at the HTTP edge,
    nothing about storage or business rules.

    What is distinctive about tasks:
        * `status` is a constrained value. We import the canonical
          `TaskStatus` enum from the ORM model so the API contract, the
          database constraint, and the status-change endpoint all share a
          single source of truth and can never drift apart.
        * There is a dedicated PATCH /tasks/{id}/status endpoint, which
          gets its own small request schema (`TaskStatusUpdate`).

    How it interacts with the rest of the app:
        * Routers use these as request bodies / response_model.
        * Services receive validated Create/Update/StatusUpdate objects.
        * `TaskResponse` is built from an ORM `Task` via from_attributes.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Import the ONE definition of allowed statuses. This is a plain enum (not
# ORM machinery), so importing it from the model keeps a single source of
# truth shared by the database column and the API.
from app.models.task import TaskStatus


class TaskBase(BaseModel):
    """Client-settable fields shared by create (and reused by the response).

    `str_strip_whitespace=True` trims input so a whitespace-only title
    collapses to "" and fails `min_length=1`.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # Required. Bounds mirror the DB column (String(255), NOT NULL).
    title: str = Field(
        min_length=1,
        max_length=255,
        description="Short title of the task.",
        examples=["Submit assignment"],
    )

    # Optional free-form details.
    description: str | None = Field(
        default=None,
        description="Optional longer description of the task.",
        examples=["Chapter 5 exercises, upload PDF"],
    )

    # Optional deadline. Pydantic parses ISO-8601 strings into datetime.
    # `None` means the task has no due date.
    due_date: datetime | None = Field(
        default=None,
        description="Optional due date/time (ISO-8601, timezone-aware).",
        examples=["2026-07-01T18:00:00Z"],
    )


class TaskCreate(TaskBase):
    """Request body for POST /tasks.

    `status` is intentionally absent: a new task always starts as
    `Pending` (database default). Status is changed only via
    PATCH /tasks/{id}/status. `id` and timestamps are server-owned.
    """


class TaskUpdate(BaseModel):
    """Request body for PUT /tasks/{id}.

    All fields optional → partial update. The service uses
    `model_dump(exclude_unset=True)` to apply only the fields the client
    actually sent. `status` is NOT here; it has its own endpoint/schema.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New title, if changing it.",
    )
    description: str | None = Field(
        default=None,
        description="New description, if changing it.",
    )
    due_date: datetime | None = Field(
        default=None,
        description="New due date, if changing it.",
    )


class TaskStatusUpdate(BaseModel):
    """Request body for PATCH /tasks/{id}/status.

    A single REQUIRED status field, validated against the TaskStatus enum,
    so only the three legal values are accepted. This is the one and only
    way clients change a task's status.
    """

    status: TaskStatus = Field(
        description="New status for the task.",
        examples=["In Progress"],
    )


class TaskResponse(TaskBase):
    """Response body for every task-returning endpoint.

    Extends the client fields with server-owned, read-only fields.
    `from_attributes=True` lets Pydantic build this directly from a
    SQLAlchemy `Task` instance (`TaskResponse.model_validate(task)`).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Server-assigned unique identifier.")
    status: TaskStatus = Field(description="Current status of the task.")
    created_at: datetime = Field(description="When the task was created (UTC-aware).")
    updated_at: datetime = Field(description="When the task was last updated (UTC-aware).")


class TaskSuggestion(BaseModel):
    """One AI-suggested task extracted from a note — a DRAFT, not persisted.

    This same model is both the LLM's structured-output target (via
    PydanticOutputParser) and the API response item, so the "extract tasks"
    endpoint returns exactly what the model produced. The client turns the ones
    the user picks into real tasks via the normal POST /tasks (TaskCreate), so a
    suggestion carries only the fields those share.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Short, imperative task title.",
        examples=["Email the advisor about the deadline"],
    )
    description: str | None = Field(
        default=None,
        description="Optional one-line detail for the task.",
        examples=["Confirm whether the Friday cutoff is firm"],
    )


class TaskSuggestionList(BaseModel):
    """Wrapper the LLM returns so its output is a JSON OBJECT, not a bare array.

    A top-level object (`{"tasks": [...]}`) is more reliable to prompt for and
    to parse across models than a bare list. `tasks` is empty when the note has
    no actionable items.
    """

    tasks: list[TaskSuggestion] = Field(
        default_factory=list,
        description="Extracted task suggestions; empty if the note has none.",
    )
