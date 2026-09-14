# Durable storage - Phase 10.5

> **Status (September 14, 2026):** implemented and passing local automated checks,
> but not signed off. The original run was interrupted and then stabilized; no
> Phase 10.5 report exists. Nothing has been verified against a real PostgreSQL
> server or a hosted deployment. `DATABASE_URL` accepts only `sqlite` and
> `postgresql+psycopg` drivers after normalization.

## Architecture

The existing services now delegate persistence to `backend/app/storage/`:

| Module | Responsibility |
| --- | --- |
| `base.py` | Bundle contract, safe errors, keys, checksum format |
| `local.py` | Development filesystem adapter with exclusive writes |
| `database.py` | SQLAlchemy-backed binary/JSON bundles; PostgreSQL BYTEA in production |
| `factory.py` | Select configured backend without changing service callers |
| `dataset_store.py` | CSV and dataset metadata persistence/lookup |
| `artifact_store.py` | Trusted pipeline serialization, lookup and metadata checks |

The existing `app/database` package retains engine/session and Alembic management.
PostgreSQL stores accounts, marketplace observations, predictions, model metadata
and dataset/model bundles. This phase uses PostgreSQL as the permitted alternative
durable backend rather than introducing a second S3 service. There is no S3 adapter.
Durability depends on a persistent PostgreSQL service with appropriate backups.

## Configuration

Development defaults are unchanged:

```dotenv
ENVIRONMENT=development
STORAGE_BACKEND=auto
```

SQLite defaults to the existing `data/marketpulse.db`. Datasets use
`DATA_DIR/processed`; models use MODEL_ARTIFACT_DIR. Existing local model binaries
and sidecars remain readable without conversion. No source files are deleted or
overwritten. Model paths must belong to the configured trusted artifact directory.

Production settings:

```dotenv
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/marketpulse?sslmode=require
STORAGE_BACKEND=database
STORAGE_MAX_BYTES=134217728
DEBUG=false
SQL_ECHO=false
CORS_ORIGINS=https://YOUR-FRONTEND.vercel.app
# Generate JWT_SECRET_KEY privately; do not use the development placeholder.
```

Use the PostgreSQL provider's TLS/certificate configuration. URL-encode reserved
characters in credentials. `postgres://` and `postgresql://` normalize to
`postgresql+psycopg://`; the psycopg dependency was already installed in Phase 1.
Production rejects SQLite or `STORAGE_BACKEND=local`. `auto` chooses local only in
development and database elsewhere. Environment processes override dotenv files.
No production secret is stored in the repository.

DATABASE_URL is now a required private Render setting. The Blueprint does not
provision a paid database or choose a retention plan. Provide an existing durable
database URL. DATA_DIR/MODEL_ARTIFACT_DIR are not production output locations.
The bundled demo fixture is still a read-only packaged input.

## Migration and existing data

Normal application startup applies Alembic migration `0005`. Alternatively, from
backend with the target database environment already configured:

```shell
python -m alembic upgrade head
```

Migration 0005 only adds `stored_objects`, with composite namespace/key primary
key, binary payload, JSON manifest, size, SHA-256 and creation timestamp. It
does not rewrite existing application tables, local files or model records.
Alembic URL interpolation now handles percent-encoded credentials correctly.

Changing DATABASE_URL is not a data transfer. No production database URL was
available during implementation, so no development files or database rows were
copied to an external service. Existing data remains on this machine. New builds
and training runs in production write directly to PostgreSQL without local output.

For a fresh deployment, migrate the empty database and explicitly import data or
load the bundled DEMO fixture, then build/train through the existing APIs. For
preserving a development history on a production database, a separate operator
transfer must copy application rows with their relationships and rewrite legacy
absolute dataset/model references. This phase does not silently copy private
accounts, adopt unknown pickle files or activate a replacement model. Do not
point production at a copied SQLite database or merely copy a local path string.

Back up the PostgreSQL database including `stored_objects` and all model/prediction
tables together. Verify a restore before relying on it. Downgrading 0005 drops the
storage table; never downgrade without a backup. No downgrade was run on development.

## Persistence and consistency

- Each database row publishes a binary file and its metadata in one transaction.
  Dataset CSV and metadata, or model pickle and metadata, cannot be half-published.
- Object keys are immutable through the adapter. Duplicate writes fail; they never
  replace the stored binary. Local writes use exclusive creation as well.
- References use `dbstore://datasets/<filename>.csv` or
  `dbstore://artifacts/model_vN.pkl`. They are internal identifiers, not URLs to fetch.
- New manifests include storage format version 1, key, byte count and SHA-256.
  Models also record Python, scikit-learn and joblib versions. Checksums are
  verified before parsing/deserialization, and new model records bind their digest
  to the artifact manifest through `hyperparameters.artifact_storage`.
- Model version, algorithm, feature names and dataset identity must match the
  saved manifest. Existing prediction feature/model checks are preserved.
- Metadata/CSV row-count mismatches fail; corrupt catalog sidecars do not hide all
  valid datasets. Missing objects retain explicit missing-data/model behavior.
- A model bundle is persisted before activating its database metadata record.
  If activation fails, the prior active model remains and an unused bundle may
  remain. Version allocation includes these bundles so they are not overwritten.
- Local crash leftovers similarly remain reserved. No automatic deletion/cleanup
  or artifact retention job is introduced.
- Storage failures return a sanitized HTTP 503 with `storage_unavailable` context;
  model integrity failures retain a specific artifact error. No local fallback or
  automatic retraining masks an outage.

Checksums detect corruption, not malicious authorship. Pickle/joblib can execute
code. Only server-generated artifacts in operator-controlled storage are trusted.
There is no model-file upload route. CSV/JSON marketplace import does not load
models. Restrict database and filesystem write access accordingly.

## Limits and verification

This MVP serializes/loads complete files in memory. The default binary limit is
128 MiB, configurable up to 512 MiB. This is not a streaming object store and does
not cap total database size. Budget database space/backups and API memory for ML.
Preview responses remain row-bounded, but checksum verification reads the full CSV.
Large-scale object storage can be added later behind the same adapters.

Training still uses one worker/instance. Bundle uniqueness protects against
overwrites, but the existing process-local lock is not distributed training or
activation coordination. Cross-service transactional activation/cleanup is not
introduced. No features, scoring formulas, targets or ML selection rules changed.

Tests cover local/database adapters, immutable writes, missing objects, corruption,
metadata binding, unavailable storage, configuration, migrations and both full API
journeys. SQLite provides the isolated database-adapter test runtime. PostgreSQL
DDL generation covers every revision, but it does not prove live PostgreSQL behavior.

To run the opt-in real PostgreSQL test, set TEST_POSTGRES_URL privately to a test
database URL whose user may create schemas, then run from backend:

```shell
python -m pytest tests/test_postgresql.py -p no:cacheprovider -rs
```

The integration test creates a unique schema, applies migrations, preserves a
preexisting user, compares model schema and checks persistence after reconnect.
It drops only its generated schema afterward. No server/URL was available here;
this test is skipped until configured. Managed backups, failover and hosted
deployment have not been verified.

References: [SQLAlchemy PostgreSQL types and psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html),
[Alembic offline SQL generation](https://alembic.sqlalchemy.org/en/latest/offline.html).
