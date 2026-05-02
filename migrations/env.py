"""Alembic env.py — async, reads DATABASE_URL from .env so the same migration runs
locally against the Docker Postgres and in prod against managed Postgres (Neon, RDS, …).

Hand-edited from the alembic-generated async template:
- DATABASE_URL pulled from environment (loaded via python-dotenv) instead of alembic.ini.
- target_metadata wired to SQLModel.metadata so future autogenerate diffs see our models
  once they're imported below (B1 will add the imports).
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from env. asyncpg expects no `?sslmode=...` in the URL
# (the driver handles SSL via connect_args), so a managed-Postgres URL with that
# query string would need to be cleaned. Local Docker URL has no such suffix.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)

# target_metadata: when SQLModel models are defined (B1) and imported here,
# `alembic revision --autogenerate` will diff them against the live DB to produce
# migration scripts. Until then it stays None and migrations must be hand-written.
from sqlmodel import SQLModel  # noqa: E402

# Importing the models registers their tables in SQLModel.metadata so
# `alembic revision --autogenerate` can diff them against the live DB.
from backend.db import models  # noqa: F401, E402

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emits SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (real DB connection)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
