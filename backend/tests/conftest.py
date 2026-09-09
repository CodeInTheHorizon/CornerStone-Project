"""Shared pytest fixtures.

Tests run against a throwaway SQLite file so they never touch the
development database.
"""

import os
import tempfile
from pathlib import Path

# Must be set before app.config is imported anywhere.
_tmp_db = Path(tempfile.gettempdir()) / "marketpulse_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.as_posix()}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    import app.models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
