"""Persistence, corruption, immutability and service integration contracts."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database.migrate import upgrade_to_head
from app.storage.base import StorageError, StorageConflict, StorageIntegrityError
from app.storage.local import LocalStore
from app.storage.database import DatabaseStore, StoredObject
from app.storage.artifact_store import ArtifactStore


@pytest.fixture(params=['local', 'database', 'postgresql'])
def store(request, tmp_path):
    if request.param == 'local':
        yield LocalStore(tmp_path / 'objects', 1024 * 1024)
    elif request.param == 'database':
        engine = create_engine(f"sqlite:///{(tmp_path / 'store.db').as_posix()}")
        upgrade_to_head(engine)
        yield DatabaseStore(engine, 'artifacts', 1024 * 1024)
        engine.dispose()
    else:
        # Same contract against a real server, in a throwaway schema.
        if not os.environ.get('TEST_POSTGRES_URL'):
            pytest.skip('TEST_POSTGRES_URL not configured; no PostgreSQL server available')
        url = make_url(os.environ['TEST_POSTGRES_URL']).set(drivername='postgresql+psycopg')
        schema = 'mp_store_' + uuid4().hex
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
        try:
            upgrade_to_head(engine)
            yield DatabaseStore(engine, 'artifacts', 1024 * 1024)
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def test_bundle_round_trip_and_no_overwrite(store):
    meta = store.put('model_v1.pkl', b'original', {'model_version': 'v1'})
    assert meta['storage']['sha256'] == hashlib.sha256(b'original').hexdigest()
    assert store.key_from_location(store.location('model_v1.pkl')) == 'model_v1.pkl'
    assert store.get('model_v1.pkl') == (b'original', meta)
    with pytest.raises(StorageConflict):
        store.put('model_v1.pkl', b'replacement', {})
    assert store.get('model_v1.pkl')[0] == b'original'


def test_missing_and_invalid_keys(store):
    assert store.get('missing.pkl') is None
    for key in ['../outside.pkl', '/absolute.pkl', 'https://example.com/model.pkl', 'a\\b']:
        with pytest.raises(StorageIntegrityError):
            store.get(key)


def test_payload_corruption_detected_before_deserialization(store):
    store.put('model_v1.pkl', b'original', {})
    if isinstance(store, LocalStore):
        Path(store.location('model_v1.pkl')).write_bytes(b'corrupt')
    else:
        with store.engine.begin() as connection:
            connection.execute(update(StoredObject).values(payload=b'corrupt'))
    with pytest.raises(StorageIntegrityError):
        store.get('model_v1.pkl')


def test_bundle_metadata_corruption(store):
    store.put('model_v1.pkl', b'original', {})
    if isinstance(store, LocalStore):
        path = store._sidecar('model_v1.pkl')
        meta = json.loads(path.read_text())
        meta['storage']['key'] = 'model_v2.pkl'
        path.write_text(json.dumps(meta))
    else:
        with store.engine.begin() as connection:
            connection.execute(update(StoredObject).values(sha256='0'*64))
    with pytest.raises(StorageIntegrityError):
        store.get('model_v1.pkl')


def test_size_limit_does_not_publish(store):
    store.max_bytes = 4
    with pytest.raises(StorageError):
        store.put('too_large.pkl', b'12345', {})
    assert store.get('too_large.pkl') is None


def test_trusted_legacy_local_model_and_metadata_binding(tmp_path):
    import joblib
    root = tmp_path / 'models'
    root.mkdir()
    joblib.dump({'legacy': True}, root / 'model_v1.pkl')
    record = SimpleNamespace(artifact_path=str(root / 'model_v1.pkl'), model_version='v1',
                             hyperparameters={}, algorithm='fixture', feature_names=[])
    artifacts = ArtifactStore(root)
    assert artifacts.load(record) == {'legacy': True}
    location, info = artifacts.save({'new': True}, 'v2', {
        'model_version': 'v2', 'model_type': 'fixture', 'feature_names': [], 'dataset_id': 'data1'})
    record.artifact_path = location
    record.model_version = 'v2'
    record.hyperparameters = {'dataset_id': 'data1', 'artifact_storage': info}
    assert artifacts.load(record) == {'new': True}
    record.model_version = 'v3'
    with pytest.raises(StorageIntegrityError):
        artifacts.load(record)


def test_no_arbitrary_model_path(tmp_path):
    outside = tmp_path / 'untrusted.pkl'
    outside.write_bytes(b'never deserialize')
    record = SimpleNamespace(artifact_path=str(outside))
    with pytest.raises(StorageIntegrityError):
        ArtifactStore(tmp_path / 'trusted').load(record)


def test_database_backend_unavailable_is_sanitized(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path/'missing'/'database.db').as_posix()}")
    try:
        with pytest.raises(StorageError, match='Durable storage is unavailable') as error:
            DatabaseStore(engine, 'artifacts', 1024).get('model_v1.pkl')
        assert str(tmp_path) not in str(error.value)
    finally:
        engine.dispose()


@pytest.mark.parametrize('url', ['postgres://user:pass@localhost/db', 'postgresql://user:pass@localhost/db', 'postgresql+psycopg://user:pass@localhost/db'])
def test_production_configuration_uses_postgres(url):
    config = Settings(_env_file=None, ENVIRONMENT='production', DATABASE_URL=url,
                      STORAGE_BACKEND='auto', JWT_SECRET_KEY='test-only-'*6,
                      CORS_ORIGINS=['https://marketpulse.vercel.app'])
    assert config.DATABASE_URL == 'postgresql+psycopg://user:pass@localhost/db'
    assert config.storage_backend == 'database'


@pytest.mark.parametrize('values', [{'DATABASE_URL': 'sqlite:///unsafe.db'}, {'DATABASE_URL': 'postgresql://user:pass@localhost/db', 'STORAGE_BACKEND': 'local'}])
def test_production_cannot_fall_back_to_ephemeral_storage(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT='production', JWT_SECRET_KEY='test-only-'*6,
                 CORS_ORIGINS=['https://marketpulse.vercel.app'], **values)


@pytest.mark.parametrize('url', ['mysql://user:s3cret-pw@localhost/db', 'postgresql+psycopg2://user:s3cret-pw@localhost/db',
                                 'postgresql+asyncpg://user:s3cret-pw@localhost/db', 'not a url s3cret-pw'])
def test_unsupported_database_urls_rejected_without_echo(url):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, DATABASE_URL=url)
    assert 's3cret-pw' not in str(error.value)


def test_development_defaults_to_local_sqlite():
    config = Settings(_env_file=None, ENVIRONMENT='development')
    assert config.is_sqlite and config.storage_backend == 'local'
    assert Settings(_env_file=None, DATABASE_URL='postgres://u:p@localhost/db').storage_backend == 'local'


def test_dataset_availability_follows_storage_backend(monkeypatch, tmp_path):
    from app.config import settings
    from app.services import dataset_service
    stored = tmp_path / 'dataset.csv'
    stored.write_text('price\n1\n')
    assert dataset_service.dataset_available({'csv_path': str(stored)})
    assert not dataset_service.dataset_available({'csv_path': str(tmp_path / 'gone.csv')})
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'database')
    assert dataset_service.dataset_available({'csv_path': 'dbstore://datasets/marketpulse_dataset_x.csv'})
    assert not dataset_service.dataset_available({})


def test_storage_outage_returns_503(client, monkeypatch):
    from app.services import dataset_service
    from uuid import uuid4
    token = client.post('/auth/register', json={'email':f'storage-{uuid4().hex}@example.com','password':'marketpulse1'}).json()['access_token']
    def unavailable():
        raise StorageError('Durable storage is unavailable.')
    monkeypatch.setattr(dataset_service, 'list_datasets', unavailable)
    response = client.get('/ml/dataset/status', headers={'Authorization': 'Bearer '+token})
    assert response.status_code == 503
    assert response.json()['detail']['status'] == 'storage_unavailable'


def test_dataset_row_count_consistency(store, tmp_path):
    from app.storage.dataset_store import DatasetStore
    dataset_store = DatasetStore(tmp_path)
    dataset_store.backend = store
    key = 'marketpulse_dataset_20260914T000000_fixture.csv'
    metadata = store.put(key, b'price\n100\n200\n', {
        'dataset_id': 'fixture', 'csv_path': store.location(key), 'total_output_rows': 2})
    assert len(dataset_store.load(metadata)) == 2
    metadata = {**metadata, 'total_output_rows': 3}
    with pytest.raises(StorageIntegrityError, match='row count'):
        dataset_store.load(metadata)
