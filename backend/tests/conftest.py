"""Shared pytest fixtures.

Tests run against a throwaway SQLite file so they never touch the
development database.
"""

import os
import tempfile
from pathlib import Path

# Must be set before app.config is imported anywhere.
_test_storage = tempfile.TemporaryDirectory(prefix="marketpulse_tests_", ignore_cleanup_errors=True)
_tmp_db = Path(_test_storage.name) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-not-used-anywhere-real"
os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["MODEL_ARTIFACT_DIR"] = str(Path(_test_storage.name) / "artifacts")
os.environ["FLIPKART_WEB_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.database.migrate import upgrade_to_head  # noqa: E402
from app.main import app  # noqa: E402
from app.services import dataset_service  # noqa: E402

# Preserve the bundled demo input, but never write generated test datasets
# into the application's processed-data directory.
dataset_service.PROCESSED_DIR = Path(_test_storage.name) / "processed"


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    import app.models  # noqa: F401  (registers models on Base.metadata)

    # Build the schema the same way production does -- by running the
    # migrations. Using create_all() here would diverge from the real startup
    # path and collide with it when the app's lifespan runs.
    _drop_everything()
    upgrade_to_head(engine)
    yield
    _drop_everything()
    engine.dispose()
    _test_storage.cleanup()


def _drop_everything() -> None:
    """Reset the throwaway database, history included.

    A previous run that crashed would otherwise leave rows behind and make
    uniqueness assertions fail confusingly.
    """
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Direct database session, for assertions the API does not expose."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def isolated_rate_limits(monkeypatch):
    # Every test starts a new window. Dedicated abuse tests exercise real low limits.
    from app.auth import rate_limits
    from app.config import settings
    monkeypatch.setattr(rate_limits, "store", rate_limits.MemoryStore())
    for category in ("LOGIN", "REGISTER", "PREDICT", "COLLECT", "BUILD", "IMPORT", "DEMO", "TRAIN"):
        monkeypatch.setattr(settings, "RATE_LIMIT_" + category, 1000)
