"""Schema management via Alembic.

Replaces the create_all() used up to Phase 3, which could create tables but
never add a column to an existing one -- so a database created by an earlier
phase silently lacked the fields added later.

`upgrade_to_head()` handles three cases:

1. **Empty database** -- runs every migration from scratch.
2. **Database created by create_all() before migrations existed** -- stamps the
   baseline revision (rather than re-running it, which would fail on tables
   that already exist), then applies the rest. No data is touched.
3. **Already-migrated database** -- applies whatever is outstanding.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, inspect, text

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"

#: The revision whose tables create_all() would already have produced.
BASELINE_REVISION = "0001"

#: PostgreSQL advisory lock id for schema upgrades (any fixed bigint; "MPMIGRAT").
MIGRATION_LOCK_KEY = 0x4D504D4947524154


def _alembic_config(connection=None) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if connection is not None:
        # env.py migrates this exact connection rather than reopening the
        # configured application database.
        config.attributes["connection"] = connection
    return config


def _current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def _has_application_tables(connection: Connection) -> bool:
    return "users" in set(inspect(connection).get_table_names())


def upgrade_to_head(engine: Engine) -> None:
    """Bring the database up to the latest revision, preserving its data.

    Any failure propagates, so startup stops instead of serving an old schema.
    """
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            # Two instances starting together (a deploy overlapping a restart)
            # would otherwise both create the same tables and one would crash.
            # The transaction-scoped lock serializes them; the waiter then sees
            # the finished revision and has nothing to apply. Released on
            # commit or rollback, so a failed migration never leaves it held.
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
            )

        # Read state inside the lock, or a waiter would act on a stale view.
        needs_stamp = (
            _current_revision(connection) is None and _has_application_tables(connection)
        )
        config = _alembic_config(connection)

        if needs_stamp:
            # Pre-Alembic database: adopt it at the baseline instead of trying
            # to create tables that already exist.
            logger.info(
                "Existing database has no migration history; stamping baseline %s.",
                BASELINE_REVISION,
            )
            command.stamp(config, BASELINE_REVISION)

        command.upgrade(config, "head")
