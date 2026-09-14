from pathlib import Path

from app.config import settings
from app.storage.local import LocalStore


def store_for(namespace: str, local_root: Path):
    if settings.storage_backend == 'local':
        return LocalStore(local_root, settings.STORAGE_MAX_BYTES)
    from app.database import engine
    from app.storage.database import DatabaseStore
    return DatabaseStore(engine, namespace, settings.STORAGE_MAX_BYTES)
