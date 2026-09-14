"""Production configuration and real startup checks in isolated storage."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import get_db
from app.main import app


@pytest.mark.parametrize("origin", ["https://*.vercel.app", "https://example.com:bad", "http://example.com"])
def test_production_rejects_unsafe_origins(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET_KEY="test-only-" * 6, DATABASE_URL="postgresql://fixture:fixture@localhost/test", CORS_ORIGINS=[origin])


def test_environment_precedes_dotenv(tmp_path, monkeypatch):
    dotenv = tmp_path / '.env'
    dotenv.write_text('PORT=9001\nDEBUG=debug\n', encoding='utf-8')
    monkeypatch.setenv('PORT', '9002')
    monkeypatch.setenv('DEBUG', 'release')
    config = Settings(_env_file=dotenv)
    assert config.PORT == 9002
    assert config.DEBUG is False


def test_readiness_reports_database_failure(client):
    class FailedDatabase:
        def execute(self, *args):
            raise OperationalError('select', {}, Exception('private database details'))
    app.dependency_overrides[get_db] = lambda: FailedDatabase()
    try:
        response = client.get('/ready')
        assert response.status_code == 503
        assert response.json() == {'detail': 'Database unavailable.'}
        assert client.get('/health').status_code == 200  # Preserve original contract.
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_startup_and_exact_cors_with_local_database(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    variables = os.environ.copy()
    variables.update(
        ENVIRONMENT='development', STORAGE_BACKEND='local', DEBUG='release', SQL_ECHO='false',
        JWT_SECRET_KEY='isolated-production-test-secret-' * 2,
        CORS_ORIGINS='https://marketpulse-test.vercel.app,http://localhost:5173',
        DATABASE_URL=f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}",
        DATA_DIR=str(tmp_path / 'data'), MODEL_ARTIFACT_DIR=str(tmp_path / 'models'),
        HOST='127.0.0.1', PORT=str(port), LOG_LEVEL='INFO', ACCESS_LOG='false', API_PREFIX='',
    )
    with (tmp_path / 'server.log').open('w+', encoding='utf-8') as output:
        process = subprocess.Popen(
            [sys.executable, '-B', '-m', 'app.start'],
            cwd=Path(__file__).resolve().parents[1], env=variables,
            stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=2) as client:
                deadline = time.monotonic() + 40
                while True:
                    assert process.poll() is None, 'Production startup exited early'
                    try:
                        response = client.get('/ready')
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, 'Production readiness timed out'
                    time.sleep(0.2)
                assert response.json()['database'] == 'connected'
                health = client.get('/health').json()
                assert health['environment'] == 'development'
                assert health['database'] == 'connected'
                for origin, allowed in [('https://marketpulse-test.vercel.app', True), ('http://localhost:5173', True), ('https://other.vercel.app', False)]:
                    response = client.options('/auth/login', headers={
                        'Origin': origin, 'Access-Control-Request-Method': 'POST',
                        'Access-Control-Request-Headers': 'authorization,content-type',
                    })
                    assert (response.headers.get('access-control-allow-origin') == origin) is allowed
        finally:
            process.terminate()
            process.wait(timeout=10)
        output.seek(0)
        logs = output.read()
        assert 'Application startup complete' in logs
        assert variables['JWT_SECRET_KEY'] not in logs
