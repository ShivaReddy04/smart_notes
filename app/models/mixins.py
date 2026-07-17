"""app/models/mixins.py

Why this file exists:
    Holds reusable column groups that more than one ORM model needs, so a
    shared set of columns is defined exactly once (DRY). Currently this is
    `TimestampMixin`, which provides the `created_at` / `updated_at`
    columns used by both Note and Task.

    Responsibility boundary:
        Purely structural. A mixin describes columns to be merged into a
        model; it contains no validation, no queries, and no business
        rules — the same narrow contract every model file follows.

    How it interacts with the rest of the app:
        Concrete models inherit it alongside `Base`
        (e.g. `class Note(TimestampMixin, Base)`). The mixin itself is NOT
        mapped to a table; SQLAlchemy applies its `mapped_column`
        definitions to each subclass, giving every model its own copy of
        the timestamp columns.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds database-managed creation and update timestamps to a model.

    IMPORTANT: this class deliberately does NOT inherit from `Base`. If it
    did, SQLAlchemy would attempt to map it to its own table. As an
    unmapped mixin, its columns are copied into each model that inherits
    it.

    Both columns are populated by the DATABASE (server_default=now()), so
    their values are correct regardless of which process writes the row
    and never depend on the application clock. `timezone=True` stores
    PostgreSQL `timestamptz`, avoiding naive-datetime bugs.
    """

    # Set once, by the database, when the row is first inserted.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Set on insert and refreshed by SQLAlchemy on every UPDATE
    # (`onupdate`), so it always reflects the last modification time.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
