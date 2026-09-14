"""Password hashing and JWT issuing/verification.

Kept free of database and HTTP concerns so it can be unit-tested directly.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.config import settings

# bcrypt silently truncates anything past 72 bytes, so longer passwords would
# all collapse to the same hash. Reject them explicitly instead.
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what bcrypt can hash without truncation."""


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash. Never store or log the plaintext."""
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except ValueError:
        # Stored value is not a valid bcrypt hash.
        return False


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    token_version: int = 0,
) -> str:
    """Issue a signed JWT whose subject is the user id."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
        "token_version": token_version,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return the token payload, or None if it is invalid or expired."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp", "token_version"]},
        )
    except InvalidTokenError:
        return None

    # Guard against a token minted for some other purpose being replayed here.
    if payload.get("type") != "access" or type(payload.get("token_version")) is not int or payload["token_version"] < 0:
        return None
    return payload
