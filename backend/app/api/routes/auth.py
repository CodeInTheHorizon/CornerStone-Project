"""Authentication endpoints.

Logout is intentionally not a server endpoint: these are stateless JWTs, so
the client discards the token. A server-side revocation list would be a
meaningful feature, but pretending a no-op endpoint revokes anything would be
worse than not having one.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import PasswordTooLongError, create_access_token
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas.auth import Token, UserLogin, UserRead, UserRegister
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and return an access token",
)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> Token:
    try:
        user = user_service.create_user(db, payload)
    except user_service.EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    except PasswordTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    return _issue_token(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Exchange credentials for an access token",
)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = user_service.authenticate_user(db, payload.email, payload.password)

    # One message for both "no such user" and "wrong password", so the response
    # does not reveal which emails are registered.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    return _issue_token(user)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the authenticated user",
)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
