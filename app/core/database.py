"""app/core/database.py

Why this file exists:
    Owns the application's single connection to PostgreSQL and the
    machinery SQLAlchemy needs to talk to it. Everything database-related
    is created here exactly once and imported elsewhere, so the rest of
    the codebase never touches engine construction or connection pooling.

    Three things live here, each with one job:
      * `engine`        -> manages the physical connection pool to Postgres.
      * `SessionLocal`  -> a factory that produces short-lived Session
                           objects (one per request / unit of work).
      * `Base`          -> the declarative base every ORM model inherits
                           from, giving SQLAlchemy a registry of tables.

    Plus `get_db()`, the FastAPI dependency that hands a Session to a
    request handler and guarantees it is closed afterwards. Keeping this
    in one module means session lifecycle is defined in a single place
    (Single Responsibility), and higher layers depend on the abstraction
    `get_db` rather than on SQLAlchemy internals (Dependency Inversion).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Load validated settings once. If DATABASE_URL is missing/malformed the
# app fails here at import time — loudly and early — rather than on the
# first request that needs the database.
settings = get_settings()

# --- Engine -----------------------------------------------------------
# The engine is the long-lived object that owns the connection pool. It is
# created a single time for the whole process; SQLAlchemy hands out and
# reclaims pooled connections from it as sessions need them.
#
# Why these arguments:
#   pool_pre_ping=True
#       Issues a tiny "is this connection still alive?" check before each
#       checkout. Without it, a connection killed by the DB or a network
#       blip (common after idle periods) surfaces as a confusing error
#       mid-request. With it, SQLAlchemy quietly discards the dead
#       connection and opens a fresh one.
#   future=True
#       Opts into SQLAlchemy 2.0 behavior/semantics explicitly.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

# --- Session factory --------------------------------------------------
# sessionmaker is a configured factory: calling SessionLocal() yields a new
# Session bound to our engine. A Session is the unit of work — it tracks
# object changes and the transaction, and is meant to be short-lived
# (created per request, discarded after).
#
# Why these arguments:
#   autoflush=False
#       We control when pending changes are flushed (typically at commit),
#       avoiding surprise SQL emitted by unrelated reads.
#   autocommit=False
#       Transactions are explicit. Nothing is persisted until we commit,
#       which makes the unit-of-work boundary obvious and safe.
#   expire_on_commit=False
#       After commit, attributes stay loaded so we can still read an
#       object's fields (e.g. to serialize a response) without triggering
#       a fresh query against an already-closed session.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


# --- Declarative base --------------------------------------------------
class Base(DeclarativeBase):
    """The root class for all ORM models.

    Why a class (SQLAlchemy 2.0 style) instead of the legacy
    `declarative_base()` function:
        DeclarativeBase integrates with typing via `Mapped[...]` and
        `mapped_column(...)`, so model columns are statically typed and
        play well with mypy and editors. Every table model inherits from
        this so they share one metadata registry, which Alembic and
        `Base.metadata.create_all()` use to discover tables.
    """


# --- Request-scoped session dependency --------------------------------
def get_db() -> Generator[Session, None, None]:
    """Yield a database session for the lifetime of a single request.

    Why a generator dependency:
        FastAPI calls this via `Depends(get_db)`. The code before `yield`
        runs when the request starts (open a session); the code after
        `yield` runs when the request ends (close it), even if the handler
        raised. The `finally` block is the contract that guarantees the
        connection is always returned to the pool — preventing leaks that
        would otherwise exhaust the pool under load.

    Usage (in a router):
        def endpoint(db: Session = Depends(get_db)) -> ...:
            ...

    The handler receives a ready-to-use Session and never has to know how
    it was created or cleaned up.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
