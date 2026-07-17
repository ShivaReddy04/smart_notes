"""alembic/env.py

Why this file exists:
    The migration runtime executed by every Alembic command. It configures
    HOW migrations connect to the database and WHAT schema they compare
    against when autogenerating.

    The critical wiring lives here:
      * It imports `app.db.base`, which in turn imports every ORM model, so
        `Base.metadata` is fully populated. `target_metadata` then points at
        that complete metadata — letting `alembic revision --autogenerate`
        diff the live database against our models and emit accurate
        migrations. (This is the entire reason `app/db/base.py` exists.)
      * It injects the database URL from our pydantic Settings, so the
        blank `sqlalchemy.url` in alembic.ini is filled from `.env` at
        runtime — one source of truth, no secrets in committed files.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import application settings and the metadata aggregation point.
from app.core.config import get_settings

# Importing app.db.base registers ALL models on Base.metadata as a side
# effect, so autogenerate sees every table. We import Base from it directly.
from app.db.base import Base

# The Alembic Config object provides access to values in alembic.ini.
config = context.config

# Inject the real database URL from settings (alembic.ini leaves it blank).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configure Python logging from the alembic.ini sections, if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata Alembic compares the database against. Because app.db.base
# imported every model, this describes the COMPLETE intended schema.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL statements to stdout/a file without requiring a live database
    connection. Useful for generating a migration script to review or to
    hand to a DBA. `literal_binds` inlines parameter values into the SQL.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Detect column type and server-default changes, important for the
        # task_status enum and our timestamptz / default columns.
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (the usual path).

    Opens a real connection to the database and applies migrations within a
    transaction. This is what `alembic upgrade head` uses.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Alembic decides which mode to run based on how it was invoked.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
