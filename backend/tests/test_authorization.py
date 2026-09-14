"""Phase 13 authorization, revocation, abuse controls and migration regressions."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from unittest.mock import Mock

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from alembic import command

from app.auth.permissions import Role, Permission, permissions_for
from app.auth.security import create_access_token, hash_password
from app.auth import rate_limits
from app.config import settings
from app.database.migrate import _alembic_config, upgrade_to_head
from app.models import User, Prediction

@pytest.fixture(scope="module")
def password_hash():
    return hash_password("marketpulse1")

@pytest.fixture
def account(db_session, password_hash):
    ids = []
    def create(role="viewer", active=True):
        user = User(email=uuid4().hex + "@example.com", hashed_password=password_hash, role=role, is_active=active)
        db_session.add(user)
        db_session.commit()
        ids.append(user.id)
        return user, {"Authorization": "Bearer " + create_access_token(user.id, token_version=user.token_version)}
    yield create
    db_session.rollback()
    db_session.query(Prediction).filter(Prediction.user_id.in_(ids)).delete(synchronize_session=False)
    db_session.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    db_session.commit()

OPERATIONS = [
    ("/data/collect", Permission.COLLECT, "app.services.collection_service.run_collection", {"platform":"flipkart", "keyword":"earbuds"}),
    ("/data/import", Permission.IMPORT, "app.services.import_service.import_dataset", None),
    ("/data/demo/load", Permission.DEMO, "app.services.demo_service.load_demo_dataset", {}),
    ("/ml/dataset/build", Permission.BUILD, "app.services.dataset_service.build_and_store", {}),
    ("/ml/train", Permission.TRAIN, "app.services.training_service.train", {"source_types":["demo"]}),
    ("/ml/predict", Permission.PREDICT, "app.services.prediction_service.predict", {"product_key":"example"}),
]

@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("path,permission,service,payload", OPERATIONS)
def test_operation_matrix(client, account, monkeypatch, role, path, permission, service, payload):
    user, headers = account(role)
    handler = Mock(side_effect=HTTPException(418, detail="Reached service"))
    monkeypatch.setattr(service, handler)
    kwargs = {"files":{"file":("data.json", b"[]", "application/json")}} if payload is None else {"json":payload}
    response = client.post(path, headers=headers, **kwargs)
    allowed = permission in permissions_for(role)
    assert response.status_code == (418 if allowed else 403)
    assert handler.called == allowed
    if not allowed:
        assert response.json()["detail"] == "You do not have permission to perform this action."
        assert client.get("/auth/me", headers=headers).status_code == 200

@pytest.mark.parametrize("path,permission,service,payload", OPERATIONS)
def test_operations_require_authentication(client, path, permission, service, payload):
    kwargs = {"files":{"file":("data.json", b"[]")}} if payload is None else {"json":payload}
    assert client.post(path, **kwargs).status_code == 401

def test_registration_defaults_and_escalation(client):
    email = uuid4().hex + "@example.com"
    for extra in ({"role":"administrator"}, {"role":"operator"}, {"token_version":2}, {"permissions":["users:manage"]}):
        response = client.post("/auth/register", json={"email":email, "password":"marketpulse1", **extra})
        assert response.status_code == 422
    result = client.post("/auth/register", json={"email":email, "password":"marketpulse1"}).json()
    assert result["user"]["role"] == "viewer"
    assert result["user"]["permissions"] == ["workspace:read"]
    assert "hashed_password" not in result["user"] and "token_version" not in result["user"]

@pytest.mark.parametrize("role", ["viewer", "analyst", "operator"])
def test_admin_only_and_self_escalation(client, account, role):
    user, headers = account(role)
    assert client.get("/admin/users", headers=headers).status_code == 403
    assert client.patch(f"/admin/users/{user.id}/role", headers=headers, json={"role":"administrator"}).status_code == 403
    assert client.patch(f"/admin/users/{user.id}/status", headers=headers, json={"is_active":False}).status_code == 403
    assert client.post(f"/admin/users/{user.id}/revoke-sessions", headers=headers).status_code == 403

def test_admin_lifecycle_and_revocation(client, account, db_session, caplog):
    caplog.set_level("INFO")
    admin, headers = account("administrator")
    user, old = account("analyst")
    assert "hashed_password" not in client.get("/admin/users", headers=headers).text
    response = client.patch(f"/admin/users/{user.id}/role", headers=headers, json={"role":"operator"})
    assert response.status_code == 200 and "model:train" in response.json()["permissions"]
    assert client.get("/auth/me", headers=old).status_code == 401
    credentials = {"email":user.email, "password":"marketpulse1"}
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    current = {"Authorization":"Bearer " + token}
    assert client.patch(f"/admin/users/{user.id}/status", headers=headers, json={"is_active":False}).status_code == 200
    assert client.post("/auth/login", json=credentials).status_code == 403
    assert client.get("/auth/me", headers=current).status_code == 401
    assert client.patch(f"/admin/users/{user.id}/status", headers=headers, json={"is_active":True}).status_code == 200
    assert client.get("/auth/me", headers=current).status_code == 401
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    current = {"Authorization":"Bearer " + token}
    assert client.post(f"/admin/users/{user.id}/revoke-sessions", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=current).status_code == 401
    assert all(event in caplog.text for event in ["Role changed", "Account disabled", "Account reactivated", "Sessions revoked"])
    assert token not in caplog.text and "marketpulse1" not in caplog.text

def test_last_admin_and_bootstrap(client, account, db_session):
    from app.services.account_service import bootstrap_admin
    user, old = account()
    bootstrap_admin(db_session, user.email)
    assert client.get("/auth/me", headers=old).status_code == 401
    db_session.refresh(user)
    headers = {"Authorization":"Bearer " + create_access_token(user.id, token_version=user.token_version)}
    assert client.patch(f"/admin/users/{user.id}/role", headers=headers, json={"role":"viewer"}).status_code == 409
    assert client.patch(f"/admin/users/{user.id}/status", headers=headers, json={"is_active":False}).status_code == 409
    with pytest.raises(ValueError, match="already exists"):
        bootstrap_admin(db_session, user.email)
    db_session.rollback()
    other, _ = account("administrator")
    assert client.patch(f"/admin/users/{user.id}/role", headers=headers, json={"role":"viewer"}).status_code == 200
    assert client.get("/admin/users", headers=headers).status_code == 401

@pytest.mark.parametrize("path", ["/auth/logout", "/auth/revoke-sessions"])
def test_logout_revokes_all_copied_tokens(client, account, path):
    user, headers = account()
    second = client.post("/auth/login", json={"email":user.email,"password":"marketpulse1"}).json()["access_token"]
    assert client.post(path, headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me", headers={"Authorization":"Bearer "+second}).status_code == 401
    assert client.post("/auth/login", json={"email":user.email,"password":"marketpulse1"}).status_code == 200

def test_invalid_expired_legacy_and_wrong_version_tokens(client, account):
    user, headers = account()
    good = create_access_token(user.id)
    claims = jwt.decode(good, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    del claims["token_version"]
    legacy = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    tokens = ["bad.jwt", legacy, create_access_token(user.id, token_version=99), create_access_token(user.id, expires_delta=timedelta(seconds=-1))]
    for token in tokens:
        assert client.get("/auth/me", headers={"Authorization":"Bearer "+token}).status_code == 401

def test_prediction_ids_owner_only_even_for_admin(client, account, db_session):
    owner, _ = account("analyst")
    prediction = Prediction(user_id=owner.id, product_name="Private result", model_version="fixture")
    db_session.add(prediction); db_session.commit()
    for role in Role:
        _, headers = account(role)
        assert client.get(f"/ml/predictions/{prediction.id}", headers=headers).status_code == 404
        history = client.get("/ml/predictions", headers=headers).json()
        assert history["total"] == 0

def test_login_and_registration_limits_ignore_forwarded_headers(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER", 1)
    for i in range(2):
        assert client.post("/auth/login", headers={"X-Forwarded-For":f"10.0.0.{i}"}, json={"email":"missing@example.com", "password":"wrong123"}).status_code == 401
    response = client.post("/auth/login", json={})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    assert client.post("/auth/register", json={}).status_code == 422
    assert client.post("/auth/register", json={}).status_code == 429

@pytest.mark.parametrize("path,permission,service,payload", OPERATIONS)
def test_operation_limits_are_user_scoped(client, account, monkeypatch, path, permission, service, payload):
    category = {Permission.COLLECT:"COLLECT",Permission.IMPORT:"IMPORT",Permission.DEMO:"DEMO",Permission.BUILD:"BUILD",Permission.TRAIN:"TRAIN",Permission.PREDICT:"PREDICT"}[permission]
    monkeypatch.setattr(settings,"RATE_LIMIT_"+category,1)
    handler = Mock(side_effect=HTTPException(418))
    monkeypatch.setattr(service,handler)
    _, headers = account("operator")
    kwargs = {"files":{"file":("data.json", b"[]")}} if payload is None else {"json":payload}
    assert client.post(path,headers=headers,**kwargs).status_code == 418
    response = client.post(path,headers=headers,**kwargs)
    assert response.status_code == 429
    _, other = account("operator")
    assert client.post(path,headers=other,**kwargs).status_code == 418
    assert handler.call_count == 2

def test_limiter_window_expiry_and_memory_bound():
    now = [0]
    store = rate_limits.MemoryStore(clock=lambda:now[0], max_keys=2)
    assert store.consume(("login","a"),1,60) == 0
    assert store.consume(("login","a"),1,60) == 60
    assert store.consume(("login","b"),1,60) == 0
    assert store.consume(("login","c"),1,60) == 60
    now[0] = 61
    assert store.consume(("login","a"),1,60) == 0
    assert len(store.buckets) <= 2

@pytest.mark.parametrize("filename", ["data.csv", "data.json"])
def test_file_size_413(client, account, filename):
    _, headers = account("operator")
    response = client.post("/data/import", headers=headers, files={"file":(filename, b" "*(5*1024*1024+1))})
    assert response.status_code == 413 and "5 MiB" in response.text

def test_json_and_multipart_envelope_413(client):
    for path, size in [("/auth/login", settings.REQUEST_MAX_BYTES), ("/data/import", settings.IMPORT_REQUEST_MAX_BYTES)]:
        response = client.post(path, content=b"x"*(size+1), headers={"Origin":"http://localhost:5173"})
        assert response.status_code == 413
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"

def test_chunked_and_underreported_body_rejected_before_parsing():
    from app.auth.request_limits import RequestLimitsMiddleware
    async def run(headers):
        called = []
        async def app(scope, receive, send): called.append(True)
        chunks = iter([{"type":"http.request", "body":b"a"*settings.REQUEST_MAX_BYTES,"more_body":True}, {"type":"http.request","body":b"b","more_body":False}])
        async def receive(): return next(chunks)
        messages = []
        async def send(message): messages.append(message)
        await RequestLimitsMiddleware(app)({"type":"http","method":"POST","path":"/ml/predict","headers":headers},receive,send)
        assert not called and messages[0]["status"] == 413
    asyncio.run(run([]))
    asyncio.run(run([(b"content-length",b"1")]))

def test_migration_preserves_accounts(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "accounts.db").as_posix())
    try:
        with engine.begin() as connection:
            command.upgrade(_alembic_config(connection), "0007")
            connection.execute(text("INSERT INTO users (id,email,hashed_password,is_active) VALUES (1,'old@example.com','existing-hash',1),(2,'disabled@example.com','disabled-hash',0)"))
        upgrade_to_head(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT id,hashed_password,is_active,role,token_version FROM users ORDER BY id")).all() == [(1,"existing-hash",1,"viewer",0),(2,"disabled-hash",0,"viewer",0)]
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0008"
    finally:
        engine.dispose()
