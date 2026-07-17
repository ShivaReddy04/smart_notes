"""${message}

Why this file (the template) exists:
    Alembic renders this Mako template into a new migration script every
    time you run `alembic revision`. The ${...} placeholders below are
    filled in by Alembic: the revision identifiers, the creation date, and
    (for --autogenerate) the detected schema operations inside upgrade()
    and downgrade(). Editing this template changes the shape of all future
    migration files; the canonical form below is sufficient for this
    project.

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Revision identifiers used by Alembic to order and link migrations.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Apply this migration (move the schema forward)."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert this migration (roll the schema back)."""
    ${downgrades if downgrades else "pass"}
