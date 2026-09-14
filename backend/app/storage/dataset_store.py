"""Processed dataset persistence; storage references are opaque to API clients."""
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.storage.base import StorageIntegrityError
from app.storage.factory import store_for


class DatasetStore:
    def __init__(self, root: Path):
        self.backend = store_for('datasets', root)

    def save(self, result):
        meta = result.metadata
        key = f'marketpulse_dataset_{meta.generated_at:%Y%m%dT%H%M%S}_{meta.dataset_id}.csv'
        meta.csv_path = self.backend.location(key)
        meta.metadata_path = self.backend.location(key.removesuffix('.csv') + '.metadata.json')
        saved = self.backend.put(key, result.frame.to_csv(index=False).encode('utf-8'), meta.to_dict())
        meta.storage = saved['storage']

    def catalog(self):
        from app.schemas.dataset import DatasetMetadataRead
        result = []
        for _, metadata in self.backend.catalog():
            try:
                DatasetMetadataRead.model_validate(metadata)
                key = self.backend.key_from_location(metadata['csv_path'])
                if not key.startswith('marketpulse_dataset_') or not key.endswith('.csv'):
                    continue
                info = metadata.get('storage')
                if info and (not isinstance(info, dict) or info.get('key') != key or info.get('format_version') != 1):
                    continue
                result.append(metadata)
            except (ValueError, TypeError, KeyError, StorageIntegrityError):
                continue
        return sorted(result, key=lambda item: item.get('generated_at', ''), reverse=True)

    def load(self, metadata: dict, nrows=None):
        key = self.backend.key_from_location(metadata['csv_path'])
        bundle = self.backend.get(key)
        if bundle is None:
            return None
        data, stored = bundle
        if metadata.get('storage') and (stored.get('dataset_id') != metadata['dataset_id'] or stored.get('storage') != metadata['storage']):
            raise StorageIntegrityError('Dataset metadata does not match the selected file.')
        frame = pd.read_csv(BytesIO(data), nrows=nrows)
        if metadata.get('storage') and nrows is None and len(frame) != metadata['total_output_rows']:
            raise StorageIntegrityError('Dataset row count does not match metadata.')
        return frame
