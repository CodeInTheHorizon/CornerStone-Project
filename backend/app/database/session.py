"""Database engine, session factory and FastAPI session dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.base import Base

# check_same_thread is a SQLite-only connect arg; passing it to any other
# driver raises, so it is applied conditionally.
_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any missing tables.

    Phase 1 uses create_all for a fast local setup. A migration tool
    (Alembic) should replace this before the schema starts evolving in
    an environment that holds real data.
    """
    # Importing the models package registers every model on Base.metadata.
    from app import models  # noqa: F401

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db"]
