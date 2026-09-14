"""Offline PostgreSQL DDL checks and opt-in real-server migration verification.

TEST_POSTGRES_URL must name a test database whose role may create schemas.
Only a unique schema created by this test is touched, never public/application tables.
"""
from io import StringIO
import os
from uuid import uuid4

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.database import Base
from app.database.migrate import _alembic_config, upgrade_to_head
from app.storage.database import DatabaseStore


def test_complete_migration_chain_generates_postgresql_sql(monkeypatch):
    # Percent-escaped passwords must not break Alembic ConfigParser interpolation.
    monkeypatch.setattr(settings, 'DATABASE_URL', 'postgresql+psycopg://fixture:p%40ss@localhost/test')
    config = _alembic_config()
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, 'head', sql=True)
    sql = output.getvalue()
    assert 'CREATE TABLE stored_objects' in sql
    assert 'BYTEA' in sql
    assert 'RENAME source TO source_type' in sql
    assert "'0005'" in sql
    assert '_alembic_tmp' not in sql
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))


@pytest.mark.skipif(not os.environ.get('TEST_POSTGRES_URL'), reason='TEST_POSTGRES_URL not configured; no PostgreSQL server available')
def test_postgresql_upgrade_persistence_and_schema():
    url = make_url(os.environ['TEST_POSTGRES_URL'])
    assert url.get_backend_name() in {'postgres', 'postgresql'}, 'Use a dedicated PostgreSQL test database'
    url = url.set(drivername='postgresql+psycopg')
    admin = create_engine(url, connect_args={'connect_timeout': 5})
    schema = 'mp_storage_test_' + uuid4().hex
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}', 'connect_timeout': 5})
        with engine.begin() as connection:
            command.upgrade(_alembic_config(connection), '0004')
            connection.execute(text("INSERT INTO users (email, hashed_password, is_active) VALUES ('preserve@example.com', 'test-only', true)"))
        upgrade_to_head(engine)
        upgrade_to_head(engine)
        with engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM users')).scalar_one() == 1
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0005'
            assert not compare_metadata(MigrationContext.configure(connection), Base.metadata)
        store = DatabaseStore(engine, 'artifacts', 1024)
        meta = store.put('model_v1.pkl', b'persisted', {'model_version': 'v1'})
        engine.dispose()
        # Reconnect; the payload is independent of the former connection/pool.
        assert DatabaseStore(engine, 'artifacts', 1024).get('model_v1.pkl') == (b'persisted', meta)
        assert 'stored_objects' in inspect(engine).get_table_names()
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
