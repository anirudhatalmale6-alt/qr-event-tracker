"""Alembic async environment configuration.

This module wires Alembic to the application's SQLAlchemy metadata so
``alembic revision --autogenerate`` can detect schema changes, and
``alembic upgrade head`` applies them via asyncpg.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base *and* all model modules so that Alembic's autogenerate
# can see every table in MetaData.
from app.database import Base
from app.models import (  # noqa: F401 -- imported for side-effect registration
    Campaign,
    Company,
    Location,
    QRCode,
    QRLocation,
    ScanEvent,
    ScanUser,
    User,
)

# Alembic Config object -- provides access to alembic.ini values.
config = context.config

# Set up Python logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object for autogenerate support.
target_metadata = Base.metadata

# Override sqlalchemy.url with the DATABASE_URL environment variable so
# credentials never need to be committed to alembic.ini.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/qr_tracker",
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)


# ---------------------------------------------------------------------------
# Offline (SQL-script) migrations
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL statements without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online (connected) async migrations
# ---------------------------------------------------------------------------
def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Execute migrations within an existing connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using asyncpg."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entrypoint -- Alembic calls whichever mode is active.
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
