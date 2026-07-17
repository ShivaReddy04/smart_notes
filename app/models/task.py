"""app/models/task.py

Why this file exists:
    Defines the persistence shape of a task — the `tasks` table — as a
    SQLAlchemy ORM model, plus the canonical `TaskStatus` enum that fixes
    the set of legal status values.

    Responsibility boundary (same narrow contract as every model):
      * No input validation       -> `schemas/task.py`.
      * No queries                -> the task repository.
      * No business rules         -> the task service.

    How it interacts with the rest of the app:
      * Inherits from `Base`, so importing it registers the `tasks` table
        on `Base.metadata` for Alembic.
      * `TaskStatus` is the single source of truth for status values and
        is imported by the schema layer, so the API contract and the
        database constraint can never drift apart.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

# Type-only import so the `owner` relationship annotation resolves without a
# runtime circular import; the mapper is wired by the "User" string name.
if TYPE_CHECKING:
    from app.models.user import User


class TaskStatus(str, enum.Enum):
    """Allowed task statuses.

    Subclassing `str` (a "string enum") means each member IS a string, so
    it serializes cleanly to JSON ("Pending") and compares naturally with
    plain strings, while still giving us a closed, typed set of values.

    This one definition is shared by:
      * the ORM column below (enforced as a native PostgreSQL enum), and
      * the Pydantic schemas (request validation / response typing),
    guaranteeing the database constraint and the API contract stay in sync.
    """

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class Task(TimestampMixin, Base):
    """ORM model mapping the `tasks` table.

    `created_at` / `updated_at` are inherited from `TimestampMixin`.
    """

    __tablename__ = "tasks"

    # --- Identity -----------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # --- Ownership (Phase 6) -----------------------------------------
    # The user who owns this task. Indexed (every list/read is scoped by owner);
    # ON DELETE CASCADE removes a user's tasks with the user. Nullable so the
    # column can be added to a populated table (legacy rows are backfilled to the
    # first account on registration); every task created via the app sets it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # --- Core fields --------------------------------------------------
    # A task must have a title. Bounded length, enforced non-null at the
    # database level.
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional free-form details about the task. Unbounded length.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Status -------------------------------------------------------
    # Mapped to a native PostgreSQL enum named "task_status". The database
    # itself rejects any value outside TaskStatus, so invalid data cannot
    # be persisted even by code paths that bypass Pydantic.
    #   values_callable -> store the human-readable member VALUES
    #       ("In Progress") rather than the NAMES ("IN_PROGRESS").
    #   server_default  -> new rows default to "Pending" at the DB level.
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=TaskStatus.PENDING.value,
    )

    # --- Scheduling ---------------------------------------------------
    # Optional deadline. timezone=True stores timestamptz. NULL means the
    # task has no due date.
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --- Relationships -----------------------------------------------
    # The owning user (the reverse of User.tasks). Optional to mirror the
    # nullable FK above.
    owner: Mapped["User | None"] = relationship(back_populates="tasks")

    # --- Timestamps ---------------------------------------------------
    # `created_at` and `updated_at` are provided by TimestampMixin.

    def __repr__(self) -> str:
        """Concise representation for logs and debugging."""
        return (
            f"<Task id={self.id!r} title={self.title!r} "
            f"status={self.status.value if self.status else None!r}>"
        )
