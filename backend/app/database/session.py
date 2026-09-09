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
    """Prepare storage directories and bring the schema up to date.

    Uses Alembic rather than create_all(): create_all can add a missing table
    but never a missing column, so a database created by an earlier phase
    would silently lack fields added later.
    """
    # Importing the models package registers every model on Base.metadata.
    from app import models  # noqa: F401
    from app.database.migrate import upgrade_to_head

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    upgrade_to_head(engine)


__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db"]
