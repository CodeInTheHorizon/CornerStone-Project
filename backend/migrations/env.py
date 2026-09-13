"""Alembic environment.

Reads the database URL from the application settings rather than alembic.ini,
so migrations can never target a different database than the app.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base
import app.models  # noqa: F401  (registers every model on Base.metadata)

config = context.config

# A caller (app.database.migrate) may hand us the exact engine to migrate.
# Otherwise fall back to the configured application database.
_external_connection = config.attributes.get("connection")
if _external_connection is None:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None and _external_connection is None:
    # Embedded startup migrations must not reset or disable application loggers.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER most things in place; batch mode rewrites the
        # table instead, preserving data.
        render_as_batch=settings.is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def _configure_and_run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things in place; batch mode rewrites the
        # table instead, preserving data.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if _external_connection is not None:
        _configure_and_run(_external_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _configure_and_run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
