"""Migrations must produce exactly the schema the models describe.

Without this, a column added to a model but forgotten in a migration would
only surface at runtime against a real database -- which is precisely the
failure that prompted introducing Alembic.
"""

import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.database import Base
from app.database.migrate import upgrade_to_head


@pytest.fixture
def migrated_engine():
    """A fresh database built purely by running the migrations."""
    path = Path(tempfile.gettempdir()) / f"mp_migrate_{uuid.uuid4().hex}.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        upgrade_to_head(engine)
        yield engine
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_migrations_create_every_model_table(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert set(Base.metadata.tables) <= tables


def test_migrated_columns_match_the_models(migrated_engine):
    inspector = inspect(migrated_engine)

    for name, table in Base.metadata.tables.items():
        migrated = {col["name"] for col in inspector.get_columns(name)}
        declared = {col.name for col in table.columns}

        missing = declared - migrated
        extra = migrated - declared
        assert not missing, f"{name}: migration is missing {sorted(missing)}"
        assert not extra, f"{name}: migration has stale {sorted(extra)}"


def test_upgrade_is_idempotent(migrated_engine):
    # Running again on an up-to-date database must be a no-op, not an error.
    upgrade_to_head(migrated_engine)


def test_phase7_preserves_existing_prediction_on_upgrade(tmp_path):
    from alembic import command
    from sqlalchemy import text
    from app.database.migrate import _alembic_config

    engine = create_engine(f"sqlite:///{(tmp_path / 'phase6.db').as_posix()}")
    try:
        with engine.begin() as connection:
            command.upgrade(_alembic_config(connection), "0003")
            connection.execute(text("INSERT INTO users (id, email, hashed_password, is_active, created_at, updated_at) VALUES (1, 'migration@example.com', 'x', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            connection.execute(text("INSERT INTO predictions (user_id, product_name, model_version, created_at, updated_at) VALUES (1, 'Existing accessory', 'v2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        upgrade_to_head(engine)
        with engine.connect() as connection:
            row = connection.execute(text("SELECT product_name, model_version, result_payload FROM predictions")).one()
            assert tuple(row) == ("Existing accessory", "v2", None)
    finally:
        engine.dispose()


def test_pre_alembic_database_is_adopted_without_data_loss():
    """A database created before migrations existed must be adopted, not rebuilt.

    The Phase 3 shape is reproduced by upgrading to the baseline revision and
    then deleting alembic_version, which is exactly what such a database looks
    like: the old tables, and no migration history.
    """
    from alembic import command
    from sqlalchemy import text

    from app.database.migrate import _alembic_config

    path = Path(tempfile.gettempdir()) / f"mp_legacy_{uuid.uuid4().hex}.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")

    try:
        with engine.begin() as conn:
            command.upgrade(_alembic_config(conn), "0001")

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_active,"
                    " created_at, updated_at)"
                    " VALUES ('legacy@example.com', 'x', 1,"
                    " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            # Erase the history, leaving a genuine pre-Alembic database.
            conn.execute(text("DROP TABLE alembic_version"))

        upgrade_to_head(engine)

        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("marketplace_snapshots")}
        assert "collection_run_id" in columns, "Phase 4 columns must be added"

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        assert count == 1, "existing rows must survive the migration"
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)
