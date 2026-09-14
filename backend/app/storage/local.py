"""Development filesystem adapter; never replaces existing files."""
import json
import os
from pathlib import Path

from app.storage.base import StorageError, StorageConflict, StorageIntegrityError, seal, valid_key, verify


class LocalStore:
    def __init__(self, root: Path, max_bytes: int):
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def location(self, key: str) -> str:
        path = self.root / valid_key(key)
        if path.resolve().parent != self.root:
            raise StorageIntegrityError("Storage path leaves its configured directory.")
        return str(path)

    def key_from_location(self, location: str) -> str:
        path = Path(location).resolve()
        if path.parent != self.root:
            raise StorageIntegrityError("Storage path leaves its configured directory.")
        return valid_key(path.name)

    def _sidecar(self, key: str) -> Path:
        return Path(self.location(str(Path(key).with_suffix('.metadata.json'))))

    def put(self, key: str, data: bytes, metadata: dict) -> dict:
        metadata = seal(data, metadata, key, self.max_bytes)
        payload = (json.dumps(metadata, indent=2, allow_nan=False) + '\n').encode()
        path = Path(self.location(key))
        sidecar = self._sidecar(key)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if sidecar.exists():
                raise StorageConflict("A stored version already exists.")
            with path.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Sidecar is the publication marker; failures leave reserved orphan files.
            with sidecar.open('xb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise StorageConflict("A stored version already exists.") from None
        except OSError:
            raise StorageError("Local storage is unavailable.") from None
        return metadata

    def get(self, key: str) -> tuple[bytes, dict] | None:
        path = Path(self.location(key))
        try:
            with path.open('rb') as stream:
                data = stream.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise StorageError("Stored file exceeds STORAGE_MAX_BYTES.")
            sidecar = self._sidecar(key)
            metadata = json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
            if not isinstance(metadata, dict):
                raise StorageIntegrityError("Invalid stored metadata.")
            verify(data, metadata, key, legacy=True)
            return data, metadata
        except FileNotFoundError:
            return None
        except (ValueError, UnicodeError):
            raise StorageIntegrityError("Invalid stored metadata.") from None
        except OSError:
            raise StorageError("Local storage is unavailable.") from None

    def catalog(self) -> list[tuple[str, dict]]:
        result = []
        try:
            for path in self.root.glob('*.metadata.json'):
                try:
                    self.key_from_location(str(path))
                    metadata = json.loads(path.read_text(encoding='utf-8'))
                    if isinstance(metadata, dict):
                        result.append((path.name, metadata))
                except (ValueError, OSError, StorageIntegrityError):
                    continue
        except OSError:
            raise StorageError("Local storage is unavailable.") from None
        return result

    def keys(self) -> list[str]:
        try:
            return [path.name for path in self.root.iterdir() if path.is_file()] if self.root.exists() else []
        except OSError:
            raise StorageError("Local storage is unavailable.") from None
