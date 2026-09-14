"""FastAPI dependencies for authenticated routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models import User
from app.services import user_service

# auto_error=False so a missing header produces our own 401 with a
# WWW-Authenticate challenge, rather than a bare 403 from the security scheme.
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to a live, active user."""
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _UNAUTHORIZED

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isascii() or not subject.isdigit() or len(subject) > 18:
        raise _UNAUTHORIZED

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise _UNAUTHORIZED from None

    if user_id <= 0:
        raise _UNAUTHORIZED

    # Look the user up every request: a token must stop working as soon as the
    # account is deleted or deactivated.
    user = user_service.get_user_by_id(db, user_id)
    if user is None:
        raise _UNAUTHORIZED

    if payload["token_version"] != user.token_version:
        raise _UNAUTHORIZED

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    return user


def require_permission(permission):
    """Resolve current database permissions on every request."""
    import logging
    from app.auth.permissions import permissions_for
    def check(user: User = Depends(get_current_user)) -> User:
        if permission not in permissions_for(user.role):
            logging.getLogger(__name__).warning("Permission denied user_id=%s permission=%s", user.id, permission)
            raise HTTPException(403, detail="You do not have permission to perform this action.")
        return user
    return check
