"""User lookup and creation.

Sits between the API layer and the ORM so route handlers stay thin.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import UserRegister


class EmailAlreadyRegisteredError(Exception):
    """Raised when registering an email that already exists."""


# A real bcrypt hash of a throwaway value. Verifying against it costs the same
# work as verifying a genuine user, which keeps the "no such user" path from
# returning noticeably faster and leaking which emails are registered.
_TIMING_EQUALIZER_HASH = (
    "$2b$12$ujT7kXWb/et8kwH6OZJhzekHgLoKpalt.OXPxuLmeNNExnt499L4m"
)


def _normalize_email(email: str) -> str:
    """Emails are case-insensitive in practice; store and compare lowercased."""
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(
        select(User).where(func.lower(User.email) == _normalize_email(email))
    ).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, payload: UserRegister) -> User:
    """Create a user, or raise if the email is taken."""
    if get_user_by_email(db, payload.email) is not None:
        raise EmailAlreadyRegisteredError(payload.email)

    user = User(
        email=_normalize_email(payload.email),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user when the credentials match, otherwise None.

    The password is verified even when no such user exists, so that response
    timing does not reveal which emails are registered.
    """
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, _TIMING_EQUALIZER_HASH)  # result discarded
        return None

    if not verify_password(password, user.hashed_password):
        return None
    return user
