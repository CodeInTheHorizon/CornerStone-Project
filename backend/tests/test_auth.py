"""Phase 3 tests: registration, login, token handling and route protection."""

from datetime import timedelta

import pytest

from app.auth.security import (
    MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

VALID = {
    "email": "trader@example.com",
    "password": "marketpulse1",
    "full_name": "Test Trader",
}


def register(client, **overrides):
    return client.post("/auth/register", json={**VALID, **overrides})


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------


def test_hash_is_salted_and_verifiable():
    first = hash_password("marketpulse1")
    second = hash_password("marketpulse1")

    assert first != "marketpulse1"
    # Distinct salts mean the same password never produces the same hash.
    assert first != second
    assert verify_password("marketpulse1", first)
    assert verify_password("marketpulse1", second)
    assert not verify_password("wrong-password", first)


def test_overlong_password_is_rejected_not_truncated():
    # bcrypt ignores bytes past 72; silently truncating would make every long
    # password with a shared prefix equivalent.
    with pytest.raises(PasswordTooLongError):
        hash_password("a" * (MAX_PASSWORD_BYTES + 1))


def test_verify_against_garbage_hash_is_false():
    assert not verify_password("marketpulse1", "not-a-bcrypt-hash")


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


def test_token_round_trip():
    token = create_access_token(42)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_expired_token_is_rejected():
    token = create_access_token(42, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_tampered_token_is_rejected():
    token = create_access_token(42)
    assert decode_access_token(token[:-2] + "xy") is None


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_register_returns_token_and_user(client):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == VALID["email"]
    assert body["user"]["full_name"] == "Test Trader"
    # The hash must never cross the wire.
    assert "hashed_password" not in body["user"]
    assert "password" not in body["user"]


def test_register_rejects_duplicate_email(client):
    register(client, email="dupe@example.com")
    again = register(client, email="dupe@example.com")

    assert again.status_code == 409


def test_register_is_case_insensitive_on_email(client):
    register(client, email="Case@Example.com")
    again = register(client, email="case@example.com")

    assert again.status_code == 409


@pytest.mark.parametrize(
    "password",
    ["short1", "alllettersnodigits", "12345678"],
)
def test_register_rejects_weak_passwords(client, password):
    response = register(client, email="weak@example.com", password=password)
    assert response.status_code == 422


def test_register_rejects_invalid_email(client):
    assert register(client, email="not-an-email").status_code == 422


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


def test_login_succeeds_with_correct_credentials(client):
    register(client, email="login@example.com")

    response = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": VALID["password"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(client):
    register(client, email="wrongpw@example.com")

    response = client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "not-the-password1"},
    )

    assert response.status_code == 401


def test_login_does_not_reveal_whether_email_exists(client):
    register(client, email="known@example.com")

    known = client.post(
        "/auth/login",
        json={"email": "known@example.com", "password": "wrong-password1"},
    )
    unknown = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password1"},
    )

    assert known.status_code == unknown.status_code == 401
    assert known.json()["detail"] == unknown.json()["detail"]


# --------------------------------------------------------------------------
# Protected routes
# --------------------------------------------------------------------------


def test_me_returns_the_authenticated_user(client):
    token = register(client, email="me@example.com").json()["access_token"]

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_me_requires_a_token(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_me_rejects_an_invalid_token(client):
    response = client.get(
        "/auth/me", headers={"Authorization": "Bearer not.a.token"}
    )
    assert response.status_code == 401


def test_me_rejects_a_token_for_a_deleted_user(client):
    # A token must stop working the moment the account behind it is gone.
    token = create_access_token(999_999)

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_inactive_user_cannot_log_in_or_use_a_token(client, db_session):
    from app.models import User

    token = register(client, email="inactive@example.com").json()["access_token"]

    user = (
        db_session.query(User).filter(User.email == "inactive@example.com").one()
    )
    user.is_active = False
    db_session.commit()

    assert (
        client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/auth/login",
            json={"email": "inactive@example.com", "password": VALID["password"]},
        ).status_code
        == 403
    )
