"""Alembic migration environment.

Migration engine resolves the target database from the DATABASE_URL environment
variable (identical logic to ``app.database.database``). The models module is the
single source of truth for the schema, so ``--autogenerate`` diffs the live
database against ``Base.metadata``.

Usage (from ``backend/``):

    # PostgreSQL
    DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/buildsure \
        ./venv/bin/alembic -c alembic.ini upgrade head
    DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/buildsure \
        ./venv/bin/alembic -c alembic.ini revision --autogenerate -m "change"

    # SQLite (local dev)
    ./venv/bin/alembic -c alembic.ini upgrade head
"""

import os

from alembic import context
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv(find_dotenv())

# Import every model so the metadata is complete for autogenerate.
import app.models.models as _models  # noqa: F401
from app.database.database import DATABASE_URL as APP_DEFAULT_URL

config = context.config

# If the operator has not exported DATABASE_URL, fall back to the platform
# default (local SQLite) so `alembic upgrade head` works out of the box.
DATABASE_URL = os.environ.get("DATABASE_URL") or APP_DEFAULT_URL
# ConfigParser treats '%' as interpolation syntax; escape the literal
# percent signs coming from URL-encoded passwords so the DSN is accepted.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = _models.Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()