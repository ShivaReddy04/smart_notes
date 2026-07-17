"""app/models/user.py

Why this file exists:
    Defines the persistence shape of a user account — the `users` table — as a
    SQLAlchemy ORM model (Phase 6, authentication). It is the single source of
    truth for what an account is in the database: a unique email and a bcrypt
    password HASH (never the plaintext).

    Responsibility boundary (the same narrow contract as every model):
      * No input validation      -> `schemas/user.py`.
      * No queries               -> the user repository.
      * No hashing / token logic -> `app/core/security.py` + the auth service.

    How it interacts with the rest of the app:
      * Inherits from `Base`, so importing it registers the `users` table on
        `Base.metadata` for Alembic.
      * Notes and tasks carry a `user_id` FK back to this table; the `notes` /
        `tasks` collections below are the owning side, so deleting a user
        cascades to their data (DB ON DELETE CASCADE + passive_deletes).
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

# Type-only imports so the relationship annotations resolve without a runtime
# circular import; the mappers are wired by the "Note"/"Task" string names.
if TYPE_CHECKING:
    from app.models.note import Note
    from app.models.task import Task


class User(TimestampMixin, Base):
    """ORM model mapping the `users` table.

    `created_at` / `updated_at` are inherited from `TimestampMixin`.
    """

    __tablename__ = "users"

    # --- Identity -----------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # The login identifier. Unique + indexed so lookups by email (every login)
    # are fast and duplicate accounts are rejected at the database level, not
    # just in application code. 320 = the maximum length of an email address.
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )

    # bcrypt hash of the password — NEVER the plaintext. Produced by
    # app.core.security.hash_password. A bcrypt hash is 60 chars; String(255)
    # leaves ample room.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Relationships -----------------------------------------------
    # A user owns many notes and tasks. cascade + passive_deletes means removing
    # a user removes their data via the DB's ON DELETE CASCADE (defined on the
    # child FKs), the same pattern Note uses for its images.
    notes: Mapped[list["Note"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Concise representation for logs (never includes the password hash)."""
        return f"<User id={self.id!r} email={self.email!r}>"
