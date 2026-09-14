"""PostgreSQL BYTEA bundles. Binary and metadata publish in one transaction.

SQLAlchemy's portable LargeBinary also supports isolated SQLite adapter tests.
Production configuration requires PostgreSQL; this is not a SQLite durability claim.
"""
import json

from sqlalchemy import BigInteger, DateTime, JSON, LargeBinary, String, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.storage.base import StorageError, StorageConflict, StorageIntegrityError, seal, valid_key, verify


class StoredObject(Base):
    __tablename__ = 'stored_objects'
    namespace: Mapped[str] = mapped_column(String(16), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DatabaseStore:
    def __init__(self, engine, namespace: str, max_bytes: int):
        if namespace not in {'datasets', 'artifacts'}:
            raise ValueError('Unknown storage namespace')
        self.engine, self.namespace, self.max_bytes = engine, namespace, max_bytes
        self.table = StoredObject.__table__

    def location(self, key: str) -> str:
        return f'dbstore://{self.namespace}/{valid_key(key)}'

    def key_from_location(self, location: str) -> str:
        prefix = f'dbstore://{self.namespace}/'
        if not location.startswith(prefix):
            raise StorageIntegrityError("Stored reference does not belong to the configured backend.")
        return valid_key(location[len(prefix):])

    def put(self, key: str, data: bytes, metadata: dict) -> dict:
        metadata = seal(data, metadata, key, self.max_bytes)
        json.dumps(metadata, allow_nan=False)
        try:
            with self.engine.begin() as connection:
                connection.execute(self.table.insert().values(
                    namespace=self.namespace, key=key, payload=data, manifest=metadata,
                    size_bytes=len(data), sha256=metadata['storage']['sha256'],
                ))
        except IntegrityError:
            raise StorageConflict("A stored version already exists.") from None
        except SQLAlchemyError:
            raise StorageError("Durable storage is unavailable. Retry when the database is reachable.") from None
        return metadata

    def _where(self, key: str):
        return (self.table.c.namespace == self.namespace) & (self.table.c.key == valid_key(key))

    def get(self, key: str) -> tuple[bytes, dict] | None:
        try:
            with self.engine.connect() as connection:
                # Check the recorded size before loading a potentially large BYTEA.
                size = connection.execute(select(self.table.c.size_bytes).where(self._where(key))).scalar_one_or_none()
                if size is None:
                    return None
                if size > self.max_bytes:
                    raise StorageError("Stored file exceeds STORAGE_MAX_BYTES.")
                row = connection.execute(select(self.table).where(self._where(key))).mappings().one()
            data, metadata = bytes(row['payload']), row['manifest']
            if len(data) > self.max_bytes:
                raise StorageError("Stored file exceeds STORAGE_MAX_BYTES.")
            if not isinstance(metadata, dict):
                raise StorageIntegrityError("Invalid stored metadata.")
            verify(data, metadata, key)
            if row['sha256'] != metadata['storage']['sha256'] or row['size_bytes'] != len(data):
                raise StorageIntegrityError("Storage record and manifest disagree.")
            return data, metadata
        except SQLAlchemyError:
            raise StorageError("Durable storage is unavailable. Retry when the database is reachable.") from None

    def catalog(self) -> list[tuple[str, dict]]:
        try:
            with self.engine.connect() as connection:
                return [(row.key, row.manifest) for row in connection.execute(
                    select(self.table.c.key, self.table.c.manifest).where(self.table.c.namespace == self.namespace))]
        except SQLAlchemyError:
            raise StorageError("Durable storage is unavailable. Retry when the database is reachable.") from None

    def keys(self) -> list[str]:
        return [key for key, _ in self.catalog()]
