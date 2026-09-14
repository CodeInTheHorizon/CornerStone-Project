# Phase 12 — ML Validation Hardening and Real-Data Readiness

**Date:** 14 September 2026
**Status:** Phase 12 complete. Active model still **v5** (XGBoost), **DEMO-trained**, quality status **`below_baseline`**. Forward-label boundary leak fixed. **0 LIVE observations**; no model is real-data trained.

## Headline

- **Fixed a confirmed evaluation leak.** On the DEMO dataset, 96 of 288 training
  rows took their label from a validation-period price. Labels are now generated
  inside each side of the time split.
- **Training requires explicit provenance.** DEMO data can no longer contaminate
  an IMPORTED or LIVE model by accident.
- **Every model gets a quality status**
  (`below_baseline` / `experimental` / `candidate` / `validated`), backed by
  several baselines and measured probability quality.
- **The active model is still v5,** trained on synthetic DEMO data and below its
  baseline. It was not retrained or modified. It now reads as `below_baseline`
  and is flagged as trained before this fix.
- **0 LIVE observations exist.** The Flipkart LIVE connector is gated by
  credentials and Flipkart's written approval. No model here is real-data
  trained.

The target is unchanged: `marketplace_opportunity_class`, the direction of a
listing's next observed price (±1%). It is a price-direction opportunity proxy,
**not sales demand**.

## 1. Audit (before any change)

Measured read-only against v5 and its dataset. Nothing was written.

| # | Item | Finding |
|---|---|---|
| 1 | Active model | **v5**, XGBoost, trained 2026-09-13, 35 features |
| 2 | Provenance | dataset `4675ea7921af`: 480 rows, **100% DEMO**, 79 products, 4 platforms, 2026-09-01 → 09-05 |
| 3 | Target | next-observation price direction, ±1% threshold |
| 4 | Split | temporal (train < 09-04: 288 rows; validate ≥ 09-04: 96 rows), **labels generated before splitting** |
| 5 | Class distribution | declining 173 / stable 140 / improving 71 (validation 39 / 33 / 24) |
| 6 | Metrics | accuracy 33.33%, weighted F1 31.87%, macro F1 29.8% |
| 7 | Baselines | majority 40.62%; previous direction 34.38%; always "stable" 34.38% |
| 8 | Leakage | **96/288 training labels crossed the boundary**; all 96 validation listings also appear in training (temporal by design); features are backward-looking only |
| 9 | Excluded columns | snapshot_id, product_key, external_id, product_name, currency, collection_timestamp, forward_price, forward_price_change_pct, target |
| 10 | Calibration | none. Log loss 1.644 vs 1.099 uniform; Brier 0.924 vs 0.667 uniform; ECE 0.378; mean confidence 70.7% vs 33.3% accuracy. **Overconfident and worse than uniform** on 96 rows |

## 2. Forward-label boundary leakage

**Problem.** `add_target` labelled every row from its listing's next observation
over the whole dataset, and the frame was split by date afterwards. Each
listing's last training-day row (2026-09-03) was labelled from its 2026-09-04
price, which is in the validation period.

**Fix.** The boundary is chosen first and each side is labelled separately
(`app/ml/validation.py::temporal_split`):
1. Take the distinct UTC observation dates.
2. From the latest candidate boundary backwards, label the training partition
   (rows before the boundary) and the validation partition (rows on or after it)
   independently.
3. Pick the latest boundary that leaves labelled rows on both sides with at least
   the validation share (20%).
4. Record how many labels were purged.

`add_target` now also stores `target_observed_at` (excluded from features), so
the guarantee can be asserted. `train_models` discards any target already on its
input and relabels. A frame labelled over the whole history cannot bring the
leak back.

**Effect on the DEMO data** (in-memory evaluation, not persisted):

| | Before (v5 method) | After |
|---|---:|---:|
| Training rows | 288 | 192 |
| Validation rows | 96 | 96 |
| Boundary-crossing labels | 96 | **0** (96 purged) |
| Random Forest accuracy | 32.3% | 37.5% |
| XGBoost accuracy | 33.3% | 33.3% |
| Majority baseline | 40.6% | 40.6% |

Both remain below baseline: the fixture's prices are an independent random walk.
A side effect is now reported as a training warning: with only 2026-09-01 and
09-02 labelled for training, the five trend features, which need three prior
observations, have no values before the boundary.

**Tests prove:**
- No training label uses a validation-period observation.
- Validation labels stay inside the evaluation window.
- Rewriting every future price leaves all training labels unchanged, and
  rewriting past prices leaves validation labels unchanged.
- The old global method provably crossed the boundary.
- Pre-labelled input frames are relabelled.

## 3. Product/group overlap

| Strategy | Measures | On current data |
|---|---|---|
| **Temporal (kept)** | Forecasting the next move of listings already being watched | 96 validation listings, all 96 also in training |
| Grouped temporal | Generalizing to never-seen products | **Not possible**: every product is observed on every date, so it leaves 0 validation rows |

MarketPulse forecasts listings a seller is already tracking, so temporal is the
primary strategy. Its limitation is recorded with every model:
- validation listings
- listings also in training
- unseen-product validation rows

Once at least `ML_MIN_VALIDATION_ROWS` unseen-product rows exist, their accuracy
is reported separately (`unseen_product_accuracy`).

## 4. Provenance policy (`app/ml/provenance.py`)

`POST /ml/train` now requires `source_types`. The dataset may contain only the
selected types.

| Selection | Result |
|---|---|
| `demo` | allowed: `development_demo` |
| `imported` | allowed: `imported_history` |
| `live` | allowed: `live_history` |
| `imported` + `live` | allowed only when both are selected: `imported_and_live` |
| `demo` + anything | **rejected** (`provenance_rejected`), unless `development_override=true` **and** `ENVIRONMENT=development` (`development_mixed`, capped at experimental) |
| dataset contains an unselected type | **rejected**: rebuild the dataset |

Filtering rows at training time is deliberately not offered. Market features
(category medians, listing density, competition) are computed across every
dataset row, so a LIVE row built alongside DEMO rows already carries DEMO
information.

## 5. Model quality gate (`validation.quality_gate`)

Applied in order:
1. **`below_baseline`**: accuracy ≤ majority baseline accuracy (or evidence missing → `experimental`).
2. **`experimental`**: any of DEMO data, development override, a legacy leaky
   split, or accuracy not beating the strongest naive baseline.
3. **`candidate`**: IMPORTED/LIVE data beating every baseline, but not yet
   validated.
4. **`validated`**: a candidate that also has all of:
   - ≥ 200 validation rows
   - validation labels on ≥ 2 dates
   - a Wilson 95% lower bound on accuracy above the best baseline
   - log loss better than the class prior

"Validated" never rests on a single metric. It still does not mean calibrated
probabilities or sales-demand prediction.

Status is persisted in `model_metadata.quality_status` (migration `0007`), and
the reasons are stored in `metrics.quality_reasons`.

## 6. Probability quality

Nothing is recalibrated: 96 validation rows cannot support calibration without
fitting noise. Every new model stores:
- log loss (plus uniform and class-prior log loss)
- multiclass Brier score (plus uniform)
- expected calibration error over 5 bins
- mean confidence and row count
- an assessment: `insufficient_data` (< 200 rows), `worse_than_class_prior`,
  `better_than_class_prior`, or `no_probabilities`

`calibration_status` is always `uncalibrated` (or `unavailable`), and prediction
metadata exposes it.

## 7. Baselines (all accuracies)

- **Majority baseline:** share of the validation set's most common class, kept
  for continuity.
- **Training-majority accuracy:** always predicting the training set's most
  common class, a constant guess available without hindsight.
- **Previous direction (persistence):** repeat the last observed ±1% move, falling
  back to the training majority where no previous move exists. Coverage is
  reported.

The UI and API compare model **accuracy** with these accuracies. Weighted F1 is
shown separately and never compared against a baseline.

## 8. Training metadata

**New columns:** `quality_status`, `calibration_status` (nullable; migration
`0007` adds columns only).

**New records also store, in `hyperparameters` / `metrics` and the artifact
sidecar:**
- `training_policy_version=phase12-v1`
- source policy: selected and dataset source types, profile, override
- split: strategy, boundary, training range, evaluation range, purged count,
  leakage safeguards
- data summary: observation rows, labelled rows, observation dates, validation
  label dates, unique products
- baselines and probability quality
- group overlap and unseen-product accuracy
- requirements used, and per-split class distributions

**Older records** (v1–v5) are never rewritten. `training_service.quality_report`
interprets them on read:
- status `below_baseline`, or at most `experimental`
- `legacy=true`, `leakage_safe_split=false`
- probabilities `not_measured`

## 9. Real-data readiness

LIVE (or IMPORTED) snapshots need no manual step:
1. `POST /ml/dataset/build {"source_types": ["live"]}`
2. `POST /ml/train {"source_types": ["live"]}`

Training then runs the provenance check, leakage-safe labelling, temporal split,
fitting, baseline comparison, probability measurement and the quality gate, and
versions the model. Nothing depends on DEMO-specific structure or CSV rewriting.

## 10. Minimum training requirements (configurable)

| Setting | Default | Why |
|---|---:|---|
| `ML_MIN_LABELLED_ROWS` | 100 | Labelled after purging, so validation is not a handful of rows |
| `ML_MIN_TRAINING_ROWS` | 60 | A few examples per class and feature group |
| `ML_MIN_VALIDATION_ROWS` | 20 | The smallest set that says anything; far below "validated" (200) |
| `ML_MIN_UNIQUE_PRODUCTS` | 10 | A model is not a lookup table of a few listings |
| `ML_MIN_OBSERVATION_DATES` | 4 | Structural: each side needs two dates to label anything |
| `ML_MIN_ROWS_PER_CLASS` | 5 | No class learned from one or two training examples |

Below any minimum, training returns `insufficient_data` (HTTP 422) before fitting.

## 11–12. Frontend

- **Train Model:**
  - explicit training source-type selection, with the dataset's contents shown
  - the quality section: status badge, the prominent **"This model does not
    outperform the validation baseline."** alert, and **"Development model —
    trained on synthetic DEMO data."**
  - selected source types, labelled rows, observation dates, unique products,
    split and boundary, all baselines, calibration status and probability metrics
  - a Quality column in the history table
- **Predictor:**
  - a below-baseline alert, the quality badge, calibration status, the
    previous-direction baseline and a legacy-model notice
  - the top result reads **"Highest experimental opportunity score"** unless the
    model is `candidate` or `validated`
  - saved predictions from before Phase 12 still load, with defaulted fields

Browser check (Chromium, desktop 1440×900 and mobile 390×844, isolated
database): all quality texts present, experimental label shown, no horizontal
overflow, no console errors.

## 13. Tests

`backend/tests/test_ml_validation.py` adds 52 tests covering:
1. forward-label boundary leakage (6)
2. provenance filtering (10)
3. DEMO + LIVE contamination prevention (5)
4. quality statuses (9)
5. minimum-data rejection (5)
6. baseline calculations
7. metadata persistence through the API into DB and sidecar
8. probability/calibration labelling (4)
9. backwards compatibility with legacy metadata and saved predictions (4)
10. prediction warning and label behaviour (3)

Updated for the new contract: `test_training.py`, `test_stabilization.py`,
`test_end_to_end.py` and `test_postgresql.py`. Training calls now pass
`source_types`, and the split wording and migration head changed.

| Check | Result |
|---|---|
| Full backend suite | **433 passed**, 10 skipped (PostgreSQL without a server; opt-in Flipkart test) |
| PostgreSQL 17 (disposable Docker) | **42 passed**, migrations through `0007` with schema comparison |
| Frontend build / lint / tests | passed / passed / 8 passed |

## 14. Development model and data

The development database (still at migration `0004`), v1–v5 artifacts and
processed datasets are **byte-identical** to the September 14 baseline: 159 files
hashed. No persistent model was trained and no v6 exists. Migrations `0005`–`0007`
apply at the next normal backend start and only add a table or columns.

## 15. When may a model be called real-data trained?

All of the following must hold:

1. **Genuine provenance:** trained only on `live` and/or `imported` rows, with DEMO
   absent from the dataset (`source_policy.uses_demo == false`,
   `development_override == false`).
2. **Legitimate LIVE source:** LIVE rows came through an enabled connector
   (credentials plus written approval), or imported data has documented,
   permitted origin.
3. **Enough history:** every Phase 12 minimum is met on that data, with repeated
   observations over real calendar time. One fetch is not a history.
4. **Leakage-safe training:** `training_policy_version` is present (boundary-first
   split, labels purged across the boundary).
5. **Quality:** `quality_status` is at least `candidate`, beating the majority,
   training-majority and previous-direction baselines.

Describing a model as *reliable* additionally requires `validated`: ≥ 200
validation rows over ≥ 2 dates, an accuracy lower bound above every baseline, and
log loss better than the class prior. Even then it predicts a price-direction
proxy, not sales demand, and its probabilities are uncalibrated.

## Known limitations

- 0 LIVE observations. Every current metric describes synthetic DEMO data.
- One validation date on the DEMO data, so scores carry wide uncertainty.
- Temporal validation shares listings with training; unseen-product
  generalization is unmeasured on current data.
- Trend features are empty in the DEMO training partition after purging.
- The ±1% threshold is a documented judgement call; the target is unchanged.
- No calibration is fitted; probabilities must not be read as likelihoods.
