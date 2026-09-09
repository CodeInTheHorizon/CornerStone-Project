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
from sqlalchemy import Engine, inspect

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"

#: The revision whose tables create_all() would already have produced.
BASELINE_REVISION = "0001"


def _alembic_config(connection=None) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if connection is not None:
        # env.py migrates this exact connection rather than reopening the
        # configured application database.
        config.attributes["connection"] = connection
    return config


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _has_application_tables(engine: Engine) -> bool:
    return "users" in set(inspect(engine).get_table_names())


def upgrade_to_head(engine: Engine) -> None:
    """Bring the database up to the latest revision, preserving its data."""
    needs_stamp = (
        _current_revision(engine) is None and _has_application_tables(engine)
    )

    with engine.begin() as connection:
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
