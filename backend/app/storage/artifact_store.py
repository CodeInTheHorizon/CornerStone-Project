"""Only server-trained artifacts in configured trusted storage can be loaded.

Checksums detect corruption; they do not make untrusted pickle safe. No public
model-file upload is supported. Storage write access is a code-execution trust boundary.
"""
from io import BytesIO
from pathlib import Path
import platform

import joblib
import sklearn

from app.config import settings
from app.storage.base import StorageIntegrityError
from app.storage.factory import store_for


class ArtifactStore:
    def __init__(self, root: Path):
        self.backend = store_for('artifacts', root)

    def keys(self):
        return self.backend.keys()

    def save(self, pipeline, version: str, metadata: dict):
        key = f'model_{version}.pkl'
        stream = BytesIO()
        joblib.dump(pipeline, stream)
        metadata = {**metadata, 'runtime': {'python': platform.python_version(),
                    'scikit_learn': sklearn.__version__, 'joblib': joblib.__version__}}
        saved = self.backend.put(key, stream.getvalue(), metadata)
        return self.backend.location(key), saved['storage']

    def load(self, record):
        location = record.artifact_path
        if not location:
            return None
        # Preserve the existing missing-artifact contract without opening the path.
        if settings.storage_backend == 'local' and not Path(location).exists():
            return None
        key = self.backend.key_from_location(location)
        bundle = self.backend.get(key)
        if bundle is None:
            return None
        data, meta = bundle
        expected = (record.hyperparameters or {}).get('artifact_storage')
        if expected is not None and meta.get('storage') != expected:
            raise StorageIntegrityError('Model record and artifact checksum disagree.')
        if meta.get('storage'):
            if (meta.get('model_version') != record.model_version
                    or meta.get('model_type') != record.algorithm
                    or meta.get('feature_names') != record.feature_names
                    or meta.get('dataset_id') != (record.hyperparameters or {}).get('dataset_id')):
                raise StorageIntegrityError('Model record and artifact metadata disagree.')
        elif settings.storage_backend != 'local':
            raise StorageIntegrityError('Durable artifacts require versioned checksum metadata.')
        return joblib.load(BytesIO(data))
