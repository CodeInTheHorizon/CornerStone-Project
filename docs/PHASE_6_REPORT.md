# MarketPulse AI — Phase 6 Report

**Phase:** ML Model Training
**Commit:** `a59be9c`
**Date:** 10 September 2026
**Status:** Complete — 18 files changed, +2,313 / −34

---

## Headline result

> **The trained model does not beat guessing, and that is the expected outcome.**
>
> Validation accuracy **33.3%** against a majority-class baseline of **40.6%**.
>
> The training pipeline works end to end and its honesty guards fire correctly.
> Nothing here says anything about real marketplace behaviour — see
> [Why the model does not work](#why-the-model-does-not-work).

---

## 1. Files created

| File | Purpose | Lines |
|---|---|---|
| `backend/app/ml/target.py` | Target definition and class labelling | 127 |
| `backend/app/ml/training.py` | Split, preprocessing, training, evaluation, comparison | 452 |
| `backend/app/services/training_service.py` | Orchestration, artifact + metadata persistence | 259 |
| `backend/app/schemas/training.py` | Request/response schemas | 103 |
| `backend/app/api/routes/ml.py` | `/ml/train`, `/ml/status`, `/ml/metrics` | 197 |
| `backend/tests/test_training.py` | 28 tests | 485 |
| `frontend/src/components/dashboard/TrainingResults.tsx` | Evaluation panel | 238 |
| `frontend/src/services/trainingService.ts` | Typed API client | 28 |

## 2. Files modified

`backend/app/api/router.py`, `backend/app/ml/__init__.py`,
`backend/app/schemas/__init__.py`, `backend/app/services/__init__.py`,
`backend/requirements.txt`, `frontend/src/pages/TrainModelPage.tsx`,
`frontend/src/pages/DashboardPage.tsx`, `frontend/src/types/data.ts`,
`README.md`, `CLAUDE.md`.

New dependencies: `scikit-learn==1.9.0`, `joblib==1.6.0`, `xgboost==3.4.1`.

---

## 3. Target used

`marketplace_opportunity_class` — a three-class label derived from the **next**
observation of the same listing on the same platform.

| Class | Condition | Count |
|---|---|---:|
| `declining` | next price falls more than 1% | 173 |
| `stable` | next price moves within ±1% | 140 |
| `improving` | next price rises more than 1% | 71 |

## 4. Target-generation method

```
forward_price            = next effective_price for (platform, product_key)
forward_price_change_pct = (forward_price − effective_price) / effective_price × 100

  ≤ −1%          → declining
  −1% … +1%      → stable
  ≥ +1%          → improving
```

Deterministic, reproducible, and documented in `app/ml/target.py`.

### Why forward-looking

The obvious approach — score each row from its own Phase 5 features and use
that score as the label — produces a **tautology**. The model would be handed
the same numbers the label was computed from, re-derive the formula, and score
near-perfectly while having learned nothing.

Predicting the *next* observation makes this a genuine forecasting problem: the
features describe now, the label describes what happens next, and no feature
contains the answer.

### Why price direction is the opportunity signal

MarketPulse AI is built for **sellers**. A listing whose price holds or rises
indicates a market that can bear the price — room for margin. A falling price
indicates pressure. This is the opposite of how a buyer would read the same
movement.

### What this is not

A **proxy** for near-term margin direction. **Not** a measure of sales demand.
Marketplace pages do not expose unit sales, so nothing in this system measures
how much anyone actually bought.

The 96 rows that are each listing's final observation have no successor. They
are **excluded from training**, not assigned a default class.

---

## 5. Training dataset size

| | |
|---|---:|
| Dataset rows (Phase 5 output) | 480 |
| Labellable rows | 384 |
| Unlabellable (no successor) | 96 |
| Features after exclusions | 35 |
| Distinct products | 79 |
| Platforms | 4 |
| Date range | 2026-09-01 → 2026-09-05 |
| Source types | `demo` (100% synthetic) |

## 6. Train / validation split

**Time-aware**, not random.

| Split | Range | Rows |
|---|---|---:|
| Train | `< 2026-09-04` | 288 |
| Validate | `≥ 2026-09-04` | 96 |

**Why not random.** Each listing appears on five consecutive dates. A random
split would put day 3 and day 4 of the same listing on opposite sides — rows
that are near-identical by construction. The model would score well by having
effectively already seen the validation rows. Splitting on date keeps every
listing's future strictly unseen.

Fixed seed: `RANDOM_SEED = 42`.

---

## 7. Models trained

Both candidates trained successfully. XGBoost 3.4.1 was available in this
environment; had it not been, the run would have continued with RandomForest
alone and reported XGBoost as unavailable.

## 8. Actual metrics

Measured on the 96-row held-out validation split.

| Model | Accuracy | Precision (w) | Recall (w) | F1 (weighted) | F1 (macro) |
|---|---:|---:|---:|---:|---:|
| `random_forest` | 32.3% | 27.6% | 32.3% | 29.1% | 25.9% |
| **`xgboost`** ✓ | **33.3%** | 31.9% | 33.3% | **31.9%** | 29.8% |
| *majority baseline* | *40.6%* | — | — | — | — |

### Confusion matrix — selected model (rows = actual, columns = predicted)

| | declining | stable | improving |
|---|---:|---:|---:|
| **declining** | 19 | 16 | 4 |
| **stable** | 18 | 10 | 5 |
| **improving** | 11 | 10 | 3 |

Predictions are scattered across all three classes with no diagonal
concentration — the signature of a model that has found no signal.

## 9. Selected model

**XGBoost**, saved as version `v2`.

## 10. Why it was selected

> Highest weighted F1 on the validation split. F1 rather than accuracy because
> the classes are imbalanced, and weighted rather than macro so each class
> counts in proportion to how often it actually occurs. Ties break toward the
> simpler model (RandomForest).

XGBoost won on F1 (31.9% vs 29.1%). Both models are below the baseline; the
selection rule picks the better of two poor options, and the system says so.

## 11. Model artifact path

```
backend/app/ml/artifacts/model_v2.pkl
backend/app/ml/artifacts/model_v2.metadata.json
```

The complete `Pipeline` (preprocessing + model) is pickled, so prediction in
Phase 7 cannot accidentally use different encoding from training.

## 12. Model version

`v2`. Version `v1` (an earlier RandomForest-only run) is **retained on disk** —
artifacts are never overwritten, because an older artifact may be what a stored
prediction was made with.

---

## 13. API endpoints implemented

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/ml/train` | Bearer | Train, evaluate, compare, persist |
| `GET` | `/ml/status` | Bearer | Active model, version, history, XGBoost availability |
| `GET` | `/ml/metrics` | Bearer | Measured evaluation for the active model |

### Error statuses

| Status | Meaning | HTTP |
|---|---|---|
| `no_dataset` | No processed dataset exists | 422 |
| `insufficient_data` | Too few rows, one class, or a single date | 422 |
| `missing_target` | Dataset has no target column | 422 |
| `missing_features` | No usable feature columns | 422 |
| `training_failed` | Every candidate model crashed | 500 |
| `not_trained` | `/ml/metrics` before any training | 404 |

## 14. Frontend changes

**Train Model page** (`/dashboard/train`)
- Model selection (Random Forest / XGBoost, disabled when unavailable)
- Train button with loading, success and error states
- Evaluation panel: headline metrics, **baseline comparison banner**, model
  comparison table, confusion matrix, split and feature provenance, and an
  expandable list of the 9 columns excluded to prevent leakage
- Training history table: version, model, date, dataset, F1, active flag

**Dashboard**
- Model Accuracy card now shows the real F1 and the active model version, with
  the baseline stated in the hint
- Demo-trained warning banner

No redesign — all existing components, tokens and layout conventions reused.

---

## 15. Tests run

```
cd backend  && .venv/Scripts/python -m pytest        # 205 passed (28 new)
cd frontend && npm run build                          # passed, no warnings
cd frontend && npm run lint                           # exit 0
playwright phase6-e2e.mjs                             # 17/17, no page errors
```

## 16. Test results

**All passing.** The 28 new tests cover: target labelling from the next
observation, determinism, unlabelled-row exclusion, majority baseline,
leakage-column exclusion, time-aware split with no overlap, single-date
rejection, RandomForest training, XGBoost training, model comparison,
reproducibility, one-class rejection, missing-target rejection, too-few-rows
rejection, resilience when one candidate crashes, artifact and metadata
persistence, version incrementing, the three endpoints, and DEMO source
labelling.

### The deliberate-leak test

`test_a_leaked_feature_would_be_detected` trains with the target's own source
column left in. It scores **>95%** and trips the suspected-leakage warning —
confirming the guard catches what it is meant to catch.

---

## Guards against inflated scores

Predicting price direction is genuinely hard. Everything that could make a
result look better than it is has been treated as a defect.

| Guard | What it prevents |
|---|---|
| Time-aware split | Near-duplicate consecutive days landing on both sides |
| Preprocessing inside the `Pipeline` | Imputer/encoder statistics leaking backwards from validation |
| 9 columns excluded, each with a recorded reason | Identifier memorisation and target reconstruction |
| Majority baseline reported beside every score | A model matching "always guess the most common class" looking successful |
| Accuracy ≥ 95% flagged as suspicious | Leakage being celebrated as skill |

### Excluded columns

| Column | Reason |
|---|---|
| `snapshot_id` | row identifier — memorisable, no predictive meaning |
| `product_key` | listing identifier — would let the model memorise listings |
| `external_id` | platform listing id — identifier, not a signal |
| `product_name` | free text identifier — high-cardinality, memorisable |
| `currency` | constant in the current data — no signal |
| `collection_timestamp` | raw timestamp — would let the model memorise dates |
| `forward_price` | derived from the future — direct target leakage |
| `forward_price_change_pct` | the target's own source — direct target leakage |
| `marketplace_opportunity_class` | the target itself |

---

## Model metadata example

`backend/app/ml/artifacts/model_v1.metadata.json` (abridged):

```json
{
  "model_version": "v1",
  "model_name": "marketpulse-opportunity-classifier",
  "model_type": "random_forest",
  "target": "marketplace_opportunity_class",
  "target_definition": "Direction of the next observed price for the same listing: improving / stable / declining, at a +/-1% threshold. A proxy for near-term margin direction, NOT a measure of sales demand.",
  "dataset_id": "56db74444fd5",
  "dataset_source_types": ["demo"],
  "dataset_platforms": ["alibaba", "amazon", "croma", "flipkart"],
  "trained_at": "2026-09-10T10:13:12.878586+00:00",
  "training_rows": 288,
  "validation_rows": 96,
  "split_strategy": "time-aware: train < 2026-09-04, validate >= 2026-09-04",
  "split_rationale": "Repeated observations of the same listing on consecutive dates make a random split leak: adjacent days are near-duplicates. Splitting on date keeps every listing's future strictly unseen.",
  "selection_rule": "Highest weighted F1 on the validation split. F1 rather than accuracy because the classes are imbalanced, and weighted rather than macro so each class counts in proportion to how often it actually occurs. Ties break toward the simpler model (RandomForest).",
  "majority_baseline": 0.4062,
  "metrics": {
    "accuracy": 0.3229,
    "precision_weighted": 0.2762,
    "recall_weighted": 0.3229,
    "f1_weighted": 0.2908,
    "f1_macro": 0.259
  },
  "confusion_matrix": [[22, 12, 5], [21, 8, 4], [12, 11, 1]],
  "confusion_labels": ["declining", "stable", "improving"],
  "class_distribution": { "declining": 173, "stable": 140, "improving": 71 },
  "notice": "Model trained on DEMO data for development/testing."
}
```

---

## Why the model does not work

The demo fixture generates each price step as an **independent random draw**:

```python
drift = rng.uniform(-0.035, 0.02)
price = price * (1 + drift)
```

Because each step is independent of everything before it, the next price
direction is **close to unpredictable by construction**. No feature computed
from the past can forecast an i.i.d. coin flip. A model scoring at or below the
baseline is the mathematically correct result.

This was predicted before any training code was written — the expectation was
"accuracy near the 45% baseline". The observed 33.3% is in that region, and the
built-in warning fired without prompting:

> The selected model's accuracy (0.3333) does not beat always guessing the most
> common class (0.4062).

**What Phase 6 demonstrates:** the training pipeline runs end to end —
target generation, leakage-safe splitting, preprocessing, two model families,
honest comparison, versioned persistence, database metadata, and a UI that
refuses to flatter the result.

**What Phase 6 does not demonstrate:** anything about real marketplace
behaviour. That requires real data, which requires marketplace access this
project does not have.

---

## 17. Known limitations

1. **No real data anywhere.** 100% synthetic. Every metric in this report
   describes a fixture, not a market.
2. **The model has no predictive power** on this data, and is below the
   baseline. Expected — see above — but it means the active model should not be
   used for any real decision.
3. **384 labelled rows over 5 dates** is a small dataset, and a single
   validation date means these scores carry wide error bars.
4. **`improving` is the minority class** (71 rows) and is predicted worst: 3
   correct out of 24.
5. **No hyperparameter tuning.** Deliberate — on a dataset this size a search
   would tune to noise and manufacture an optimistic-looking score.
6. **The ±1% class threshold is a judgement call**, chosen by inspecting class
   balance for the most even three-way split. It is documented and adjustable.
7. **Two cross-test isolation fixtures were needed** because the session-scoped
   test database accumulates rows across modules.
8. **Model artifacts are gitignored** and stored on the local filesystem.
   Render's filesystem is ephemeral, so Phase 10 will need object storage or
   retraining on deploy.

---

## What is ready for Phase 7

- A trained, versioned, loadable pipeline (`training_service.load_pipeline`)
- `ModelMetadata` rows with the active model flagged
- `/ml/status` and `/ml/metrics` for the predictor UI to read
- The `Prediction` model from Phase 1, still unused

**Carry this forward:** any prediction produced by the current model is a
prediction from a model that scores below chance on synthetic data. Phase 7
should surface model quality alongside every prediction, not just the
prediction.
