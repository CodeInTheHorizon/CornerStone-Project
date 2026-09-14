"""Immutable binary + JSON bundles shared by filesystem and database stores."""
import hashlib
import re
from typing import Protocol


class StorageError(Exception):
    """Safe public storage failure; never contains credentials or driver errors."""


class StorageIntegrityError(StorageError):
    pass


class StorageConflict(StorageError):
    pass


def valid_key(key: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", key) or ".." in key:
        raise StorageIntegrityError("Invalid storage key.")
    return key


def seal(data: bytes, metadata: dict, key: str, max_bytes: int) -> dict:
    valid_key(key)
    if len(data) > max_bytes:
        raise StorageError("Stored file exceeds STORAGE_MAX_BYTES.")
    return {**metadata, "storage": {"format_version": 1, "key": key,
            "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}}


def verify(data: bytes, metadata: dict, key: str, *, legacy: bool = False) -> None:
    info = metadata.get("storage")
    if info is None and legacy:
        return
    if (not isinstance(info, dict) or info.get("format_version") != 1
            or info.get("key") != key or info.get("size_bytes") != len(data)
            or info.get("sha256") != hashlib.sha256(data).hexdigest()):
        raise StorageIntegrityError("Stored file checksum or metadata does not match.")


class BundleStore(Protocol):
    def location(self, key: str) -> str: ...
    def key_from_location(self, location: str) -> str: ...
    def put(self, key: str, data: bytes, metadata: dict) -> dict: ...
    def get(self, key: str) -> tuple[bytes, dict] | None: ...
    def catalog(self) -> list[tuple[str, dict]]: ...
    def keys(self) -> list[str]: ...
