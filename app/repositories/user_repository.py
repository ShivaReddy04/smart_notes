"""app/repositories/user_repository.py

Why this file exists:
    The single owner of all SQL for the `users` table (Phase 6 auth). Mirrors
    the other repositories: it is the only place that touches the Session for
    users, deals in ORM `User` objects and primitives, and returns `None` for
    "not found" rather than raising (the service decides what absence means).

    One extra, auth-specific responsibility:
        `claim_unowned_content` — the "first account inherits existing data"
        behavior. When the very first user registers, the auth service calls
        this to assign every pre-auth note/task (those with a NULL owner) to
        that user. It lives here because it is a bulk UPDATE — SQL — and this
        layer owns SQL. It touches notes/tasks by design: it is a one-off user-
        provisioning step, not ongoing note/task logic.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.task import Task
from app.models.user import User


class UserRepository:
    """Encapsulates all database access for the `users` table."""

    def __init__(self, session: Session) -> None:
        """Store the request-scoped session via constructor injection."""
        self._session = session

    # --- Create -------------------------------------------------------
    def create(self, user: User) -> User:
        """Persist a new user and return it with server-generated fields
        (id, timestamps) loaded."""
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    # --- Read ---------------------------------------------------------
    def get_by_id(self, user_id: int) -> User | None:
        """Return the user with this id, or None if it does not exist."""
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Return the user with this email, or None. The caller normalizes the
        email (lowercase) so lookups are case-insensitive against stored rows."""
        statement = select(User).where(User.email == email)
        return self._session.execute(statement).scalar_one_or_none()

    def count(self) -> int:
        """Return the total number of users — used to detect the FIRST
        registration (so it can inherit any pre-auth content)."""
        return self._session.execute(select(func.count()).select_from(User)).scalar_one()

    # --- First-user provisioning -------------------------------------
    def claim_unowned_content(self, user_id: int) -> tuple[int, int]:
        """Assign every owner-less note and task to `user_id`.

        Returns `(notes_claimed, tasks_claimed)`. Only rows with a NULL owner
        are touched, so this is safe to call once for the first user; later
        users find nothing to claim. Runs as two bulk UPDATEs in one commit.
        """
        notes_claimed = self._session.execute(
            update(Note).where(Note.user_id.is_(None)).values(user_id=user_id)
        ).rowcount
        tasks_claimed = self._session.execute(
            update(Task).where(Task.user_id.is_(None)).values(user_id=user_id)
        ).rowcount
        self._session.commit()
        return notes_claimed, tasks_claimed
