"""Offline PostgreSQL DDL checks and opt-in real-server migration verification.

TEST_POSTGRES_URL must name a test database whose role may create schemas.
Only a unique schema created by this test is touched, never public/application tables.
"""
from io import StringIO
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import httpx
import pytest
from sqlalchemy import create_engine, inspect, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.database import Base
from app.database.migrate import _alembic_config, upgrade_to_head
from app.storage.base import StorageConflict
from app.storage.database import DatabaseStore, StoredObject

BACKEND = Path(__file__).resolve().parents[1]


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
    assert "'0008'" in sql
    assert 'quality_status' in sql
    assert 'token_version' in sql and 'role' in sql
    assert 'CREATE TABLE collection_attempts' in sql
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
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0008'
            assert connection.execute(text('SELECT role, token_version, is_active FROM users')).one() == ('viewer', 0, True)
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


requires_postgres = pytest.mark.skipif(
    not os.environ.get('TEST_POSTGRES_URL'),
    reason='TEST_POSTGRES_URL not configured; no PostgreSQL server available',
)


@pytest.fixture
def pg_schema():
    """A unique throwaway schema; yields (psycopg URL, schema name)."""
    url = make_url(os.environ['TEST_POSTGRES_URL']).set(drivername='postgresql+psycopg')
    admin = create_engine(url, connect_args={'connect_timeout': 5})
    schema = 'mp_test_' + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield url, schema
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def _schema_url(url, schema) -> str:
    # Percent-encoded options also exercise settings and Alembic interpolation.
    return url.update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)


@requires_postgres
def test_concurrent_startup_migrations_serialize(pg_schema):
    """Instances starting together must not crash creating the same tables."""
    url, schema = pg_schema
    start_at = time.time() + 4
    child = (
        'import time\n'
        'from sqlalchemy import create_engine\n'
        'from app.database.migrate import upgrade_to_head\n'
        f'engine = create_engine({_schema_url(url, schema)!r})\n'
        f'time.sleep(max(0, {start_at} - time.time()))\n'
        'upgrade_to_head(engine)\n'
    )
    env = dict(os.environ, ENVIRONMENT='development', STORAGE_BACKEND='local')
    processes = [subprocess.Popen([sys.executable, '-B', '-c', child], cwd=BACKEND, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                 for _ in range(4)]
    outputs = [process.communicate(timeout=300)[0] for process in processes]
    assert [process.returncode for process in processes] == [0, 0, 0, 0], outputs
    engine = create_engine(_schema_url(url, schema))
    try:
        with engine.connect() as connection:
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all() == ['0008']
    finally:
        engine.dispose()


@requires_postgres
def test_production_journey_on_postgresql(pg_schema, tmp_path):
    """Real `python -m app.start` in production mode against PostgreSQL storage.

    Covers startup migration, auth, dataset save/load, artifact save/load after a
    restart, checksum rejection, no-overwrite protection and missing objects.
    Nothing may be written to the local data or artifact directories.
    """
    url, schema = pg_schema
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    variables = dict(
        os.environ, ENVIRONMENT='production', DEBUG='false', SQL_ECHO='false', STORAGE_BACKEND='database',
        DATABASE_URL=_schema_url(url, schema), JWT_SECRET_KEY='postgres-journey-test-secret-' * 2,
        CORS_ORIGINS='https://marketpulse-test.vercel.app', HOST='127.0.0.1', PORT=str(port),
        DATA_DIR=str(tmp_path / 'data'), MODEL_ARTIFACT_DIR=str(tmp_path / 'models'),
        LOG_LEVEL='INFO', ACCESS_LOG='false', API_PREFIX='',
    )
    base_url = f'http://127.0.0.1:{port}'

    def start(name):
        log = (tmp_path / name).open('w+', encoding='utf-8')
        process = subprocess.Popen([sys.executable, '-B', '-m', 'app.start'], cwd=BACKEND, env=variables,
                                   stdout=log, stderr=subprocess.STDOUT)
        # Cold scientific-stack imports are slow on a loaded machine; a crash fails at once.
        deadline = time.monotonic() + 180
        with httpx.Client(base_url=base_url, timeout=2) as probe:
            while True:
                assert process.poll() is None, (tmp_path / name).read_text(encoding='utf-8')
                try:
                    if probe.get('/ready').status_code == 200:
                        return process, log
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline, 'PostgreSQL production startup timed out'
                time.sleep(0.25)

    def stop(process, log):
        process.terminate()
        process.wait(timeout=20)
        log.seek(0)
        output = log.read()
        log.close()
        assert variables['JWT_SECRET_KEY'] not in output
        assert not url.password or url.password not in output
        return output

    def ok(response, status=200):
        assert response.status_code == status, (response.status_code, response.text)
        return response.json()

    def login(client):
        token = ok(client.post('/auth/login', json={'email': 'pg@example.com', 'password': 'marketpulse1'}))['access_token']
        return {'Authorization': 'Bearer ' + token}

    process, log = start('first.log')
    try:
        with httpx.Client(base_url=base_url, timeout=180) as client:
            assert ok(client.get('/health'))['environment'] == 'production'
            ok(client.post('/auth/register', json={'email': 'pg@example.com', 'password': 'marketpulse1'}), 201)
            with create_engine(_schema_url(url, schema)).begin() as connection:
                connection.execute(text("UPDATE users SET role='operator' WHERE email='pg@example.com'"))
            headers = login(client)
            assert ok(client.get('/ml/dataset/status', headers=headers))['has_dataset'] is False
            assert ok(client.get('/ml/status', headers=headers))['trained'] is False
            assert ok(client.post('/data/demo/load', headers=headers))['stored'] == 480
            dataset = ok(client.post('/ml/dataset/build', headers=headers, json={'source_types': ['demo']}))
            trained = ok(client.post('/ml/train', headers=headers, json={'dataset_id': dataset['dataset_id'], 'models': ['random_forest'], 'source_types': ['demo']}))
            assert trained['model_version'] == 'v1'
            key = ok(client.get('/ml/prediction-options', headers=headers, params={'q': 'acme 20000mah'}))['products'][0]['product_key']
            request = {'product_key': key, 'dataset_id': dataset['dataset_id']}
            first = ok(client.post('/ml/predict', headers=headers, json=request))
        stop(process, log)

        # Restart: dataset and model must come back from PostgreSQL, not memory.
        process, log = start('second.log')
        with httpx.Client(base_url=base_url, timeout=180) as client:
            headers = login(client)
            status = ok(client.get('/ml/dataset/status', headers=headers))
            assert status['stored_datasets'] == 1
            assert status['latest']['csv_path'].startswith('dbstore://datasets/')
            preview = ok(client.get('/ml/dataset/preview', headers=headers, params={'dataset_id': dataset['dataset_id'], 'limit': 3}))
            assert len(preview['rows']) == 3
            assert ok(client.get('/ml/status', headers=headers))['version'] == 'v1'
            again = ok(client.post('/ml/predict', headers=headers, json=request))
            assert [row['platform'] for row in again['ranking']] == [row['platform'] for row in first['ranking']]
            assert ok(client.get('/analytics/summary', headers=headers))['latest_dataset']['file_available'] is True

            engine = create_engine(_schema_url(url, schema))
            try:
                with engine.connect() as connection:
                    rows = connection.execute(text(
                        "SELECT namespace, key, size_bytes, octet_length(payload), sha256, "
                        "encode(sha256(payload), 'hex') FROM stored_objects ORDER BY namespace")).all()
                assert [row[0] for row in rows] == ['artifacts', 'datasets']
                assert rows[0][1] == 'model_v1.pkl' and rows[1][1].endswith('.csv')
                assert all(row[2] == row[3] and row[4] == row[5] for row in rows)

                # Immutable bundles: a second write under the same key is refused.
                with pytest.raises(StorageConflict):
                    DatabaseStore(engine, 'artifacts', 1024 * 1024).put('model_v1.pkl', b'replacement', {})

                # Checksum mismatch is refused before unpickling.
                with engine.begin() as connection:
                    connection.execute(update(StoredObject).where(StoredObject.namespace == 'artifacts').values(payload=b'tampered'))
                corrupt = client.post('/ml/predict', headers=headers, json=request)
                assert corrupt.status_code == 503, corrupt.text
                assert corrupt.json()['detail']['status'] == 'corrupt_artifact'

                # A missing dataset object is reported, never fabricated.
                with engine.begin() as connection:
                    connection.execute(text("DELETE FROM stored_objects WHERE namespace = 'datasets'"))
                assert ok(client.get('/ml/dataset/status', headers=headers))['has_dataset'] is False
                assert client.get('/ml/dataset/preview', headers=headers).status_code == 404
            finally:
                engine.dispose()
        assert 'Application startup complete' in stop(process, log)
    finally:
        if process.poll() is None:
            process.kill()
    assert not (tmp_path / 'data' / 'processed').exists()
    assert not (tmp_path / 'models').exists()


@requires_postgres
def test_postgresql_account_versions_and_admin_concurrency(pg_schema):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from app.main import app
    from app.database import get_db
    from app.models import User
    from app.auth.security import create_access_token, hash_password
    from app.services.account_service import change_account

    url, schema = pg_schema
    engine = create_engine(_schema_url(url, schema))
    upgrade_to_head(engine)
    password = hash_password("marketpulse1")
    with Session(engine) as db:
        users = [User(email=f"pg-role-{i}@example.com", hashed_password=password,
                      role="administrator" if i < 2 else "analyst") for i in range(3)]
        db.add_all(users); db.commit()
        ids = [user.id for user in users]
    def get_test_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as client:
            admin_headers = {"Authorization":"Bearer " + create_access_token(ids[0])}
            analyst_headers = {"Authorization":"Bearer " + create_access_token(ids[2])}
            assert client.patch(f"/admin/users/{ids[2]}/status", headers=admin_headers, json={"is_active":False}).status_code == 200
            assert client.get("/auth/me", headers=analyst_headers).status_code == 401
            credentials = {"email":"pg-role-2@example.com", "password":"marketpulse1"}
            assert client.post("/auth/login", json=credentials).status_code == 403
            assert client.patch(f"/admin/users/{ids[2]}/status", headers=admin_headers, json={"is_active":True}).status_code == 200
            token = client.post("/auth/login", json=credentials).json()["access_token"]
            current = {"Authorization":"Bearer " + token}
            assert client.post("/auth/logout", headers=current).status_code == 204
            assert client.get("/auth/me", headers=current).status_code == 401
        # Two simultaneous cross-demotions must leave an active administrator.
        import threading
        barrier = threading.Barrier(2)
        def demote(actor, target):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    change_account(db, actor, target, role="viewer")
                    return 200
                except HTTPException as exc:
                    db.rollback()
                    return exc.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(demote, ids[0], ids[1]), pool.submit(demote, ids[1], ids[0])]
            results = sorted(task.result(timeout=20) for task in tasks)
        assert results == [200, 403]
        with Session(engine) as db:
            assert db.execute(text("SELECT count(*) FROM users WHERE role='administrator' AND is_active")).scalar_one() == 1
            assert db.get(User, ids[2]).token_version == 3
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
