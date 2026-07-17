"""app/db/base.py

Why this file exists:
    SQLAlchemy is only aware of a table once the Python class that maps it
    has been imported — defining a model registers it on `Base.metadata`
    as an import side effect. Tools that operate on the *whole* schema
    (Alembic autogenerate, an optional dev-time `Base.metadata.create_all`)
    therefore need a single, reliable place that imports **every** model.

    This module is that place. Its one responsibility is to aggregate the
    declarative `Base` together with all ORM models so that importing this
    single file guarantees `Base.metadata` is fully populated. Alembic's
    `env.py` imports exactly this module — never the models individually —
    which removes any chance of generating a migration against a partial
    view of the schema (e.g. silently "dropping" a table that simply was
    not imported).

    It contains no logic, no queries, and no business rules. It is purely a
    registry/aggregation point, keeping model discovery in one obvious
    location (Single Responsibility) and decoupling Alembic from the
    internal layout of the `models/` package (Dependency Inversion).
"""

# Re-export the declarative Base defined once in the core database module.
# `target_metadata = Base.metadata` in Alembic's env.py will point here.
from app.core.database import Base  # noqa: F401  (re-exported on purpose)

# --- Model registry ---------------------------------------------------
# Import every ORM model below so that merely importing this module
# registers all tables on `Base.metadata`. The `# noqa: F401` markers tell
# linters these imports are intentional even though they look "unused" —
# the import itself is the point (it triggers model registration).
#
# We are building the project one file at a time, so model modules are
# registered here the moment their file is created:
from app.models.note import Note  # noqa: F401
from app.models.note_embedding import NoteEmbedding  # noqa: F401
from app.models.note_image import NoteImage  # noqa: F401
from app.models.task import Task  # noqa: F401
