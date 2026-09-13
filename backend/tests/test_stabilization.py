"""Critical Phase 9 security, validation and failure-path regressions."""
import json
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.config import Settings, settings
from app.auth.security import decode_access_token
from app.main import app
from app.models import MarketplaceSnapshot
from app.services import user_service, dataset_service, training_service
from app.scrapers.base import NormalizedRecord
from app.scrapers.validation import validate_record


@pytest.fixture
def headers(client):
    response = client.post('/auth/register', json={'email': f'phase9-{uuid4().hex}@example.com', 'password':'marketpulse1'})
    assert response.status_code == 201
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize('value,expected', [('release',False),('debug',True),('false',False),('true',True),('0',False),('1',True)])
def test_debug_boolean_compatibility(value, expected):
    assert Settings(_env_file=None, DEBUG=value).DEBUG is expected


def test_real_environment_cors_csv_and_json(monkeypatch):
    for value in ['http://localhost:5173,http://127.0.0.1:5173', '["http://localhost:5173", "http://127.0.0.1:5173"]']:
        monkeypatch.setenv('CORS_ORIGINS', value)
        assert len(Settings(_env_file=None).CORS_ORIGINS) == 2


@pytest.mark.parametrize('values', [{'JWT_SECRET_KEY':''}, {'ENVIRONMENT':'production','JWT_SECRET_KEY':'short','DEBUG':False}, {'ENVIRONMENT':'production','JWT_SECRET_KEY':'x'*48,'DEBUG':True}, {'CORS_ORIGINS':['*']}, {'CORS_ORIGINS':['https://example.com/path']}, {'ACCESS_TOKEN_EXPIRE_MINUTES':0}, {'DEBUG':'nonsense'}])
def test_unsafe_config_rejected(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize('missing', ['exp','iat','sub'])
def test_jwt_requires_expiry_and_identity(missing):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {'sub':'1', 'iat':now, 'exp':now+60, 'type':'access'}
    claims.pop(missing)
    token = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(token) is None


def test_huge_signed_subject_rejected_cleanly(client):
    now = int(datetime.now(timezone.utc).timestamp())
    token = jwt.encode({'sub':'9'*100, 'iat':now, 'exp':now+60, 'type':'access'}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get('/auth/me', headers={'Authorization':f'Bearer {token}'}).status_code == 401


def test_password_not_echoed_in_validation(client):
    secret = 'secret-without-number'
    response = client.post('/auth/register', json={'email':'invalid', 'password':secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert 'input' not in response.text
    assert response.json()['detail'][0]['loc']


@pytest.mark.parametrize('path,payload', [('/data/collect',{'platform':'amazon','keyword':'  '}),('/data/collect',{'platform':'amazon','keyword':123}),('/ml/train',{'models':[]}),('/ml/train',{'models':['imaginary']}),('/ml/train',{'dataset_id':' '}),('/ml/dataset/build',{'platforms':['imaginary']}),('/ml/dataset/build',{'start':'2026-09-05','end':'2026-09-01T00:00:00Z'})])
def test_rejects_invalid_inputs(client, headers, path, payload):
    assert client.post(path, headers=headers, json=payload).status_code == 422


def test_history_mixed_timezone_inputs(client, headers):
    response = client.get('/data/history', headers=headers, params={'start':'2026-09-01','end':'2026-09-02T00:00:00Z'})
    assert response.status_code == 200
    assert client.get('/data/history', headers=headers, params={'platform':'invalid'}).status_code == 422


def test_import_size_and_csv_failure(client, headers):
    response = client.post('/data/import', headers=headers, files={'file':('large.json',b' '*(5*1024*1024+1),'application/json')})
    assert response.status_code == 422
    assert '5 MB' in response.text
    response = client.post('/data/import', headers=headers, files={'file':('bad.csv', ('platform,product_name\namazon,'+'x'*150000).encode(),'text/csv')})
    assert response.status_code == 422
    assert 'CSV' in response.text


def test_import_offset_survives_storage(client, headers, db_session):
    name = 'Timezone-'+uuid4().hex
    row = {'platform':'amazon','product_name':name,'collection_timestamp':'2026-09-05T02:00:00+05:30','price':100}
    response = client.post('/data/import', headers=headers, files={'file':('sample.json',json.dumps([row]),'application/json')})
    assert response.status_code == 200
    stored = db_session.query(MarketplaceSnapshot).filter_by(product_name=name).one()
    assert stored.source_type == 'imported'
    assert stored.collection_timestamp.replace(tzinfo=None) == datetime(2026,9,4,20,30)


def test_nonfinite_values_cleared():
    result = validate_record(NormalizedRecord(platform='amazon',product_name='Signal',price=float('inf'), review_count=float('nan')))
    assert result.record.price is None
    assert result.record.review_count is None
    assert len(result.warnings) == 2


def test_cors_preflight(client):
    for origin, allowed in [('http://localhost:5173',True), ('https://untrusted.example',False)]:
        response = client.options('/auth/login',headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
        assert (response.headers.get('access-control-allow-origin') == origin) is allowed


def test_registration_race_rolls_back(monkeypatch, db_session):
    from app.schemas.auth import UserRegister
    calls = iter([None, object()])
    monkeypatch.setattr(user_service,'get_user_by_email',lambda *args:next(calls))
    def conflict(): raise IntegrityError('insert',{},Exception('duplicate'))
    monkeypatch.setattr(db_session,'commit',conflict)
    with pytest.raises(user_service.EmailAlreadyRegisteredError):
        user_service.create_user(db_session,UserRegister(email='race@example.com',password='marketpulse1'))
    assert not db_session.new


def test_training_busy_is_conflict(client, headers):
    assert training_service._TRAINING_LOCK.acquire(blocking=False)
    try:
        response=client.post('/ml/train',headers=headers,json={})
        assert response.status_code == 409
        assert response.json()['detail']['status'] == 'training_busy'
    finally: training_service._TRAINING_LOCK.release()


def test_artifact_version_skips_orphan(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(training_service,'ARTIFACT_DIR',tmp_path)
    (tmp_path/'model_v900.pkl').write_bytes(b'preserve')
    assert training_service._next_version(db_session) == 'v901'
    assert (tmp_path/'model_v900.pkl').read_bytes() == b'preserve'


def test_corrupt_metadata_does_not_hide_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_service,'PROCESSED_DIR',tmp_path)
    for index, content in enumerate(['[]','{}','null','{"generated_at":null}']):
        (tmp_path/f'marketpulse_dataset_{index}.metadata.json').write_text(content)
    assert dataset_service.list_datasets() == []


def test_server_failure_is_generic(client, headers, monkeypatch, caplog):
    from app.services import analytics_service
    def crash(*args): raise RuntimeError('sensitive-content-do-not-disclose')
    monkeypatch.setattr(analytics_service,'summary',crash)
    with TestClient(app,raise_server_exceptions=False) as safe_client:
        response=safe_client.get('/analytics/summary',headers={**headers, 'Origin':'http://localhost:5173'})
    assert response.headers['access-control-allow-origin']=='http://localhost:5173'
    assert response.status_code == 500
    assert 'sensitive-content-do-not-disclose' not in response.text
    assert 'sensitive-content-do-not-disclose' not in caplog.text
    assert 'RuntimeError' in caplog.text


def test_collection_policy_consistent(client, headers, monkeypatch):
    from app.scrapers.amazon import AmazonCollector
    monkeypatch.setattr('app.services.collection_service.get_collector',lambda _: AmazonCollector(access_key='fixture',secret_key='fixture',partner_tag='fixture'))
    response=client.post('/data/collect',headers=headers,json={'platform':'amazon','keyword':'earbuds'})
    assert response.status_code == 501
    assert 'deprecated' in response.text
    summary=client.get('/analytics/summary',headers=headers).json()
    status=client.get('/data/status',headers=headers).json()
    assert not status['platforms']['amazon']['available']
    assert 'amazon' not in summary['available_live_platforms']
