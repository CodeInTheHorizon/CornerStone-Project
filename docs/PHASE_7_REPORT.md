# Phase 7 — Prediction and Cross-Platform Opportunity Score

Implemented September 10, 2026 on top of Phase 6, without retraining or replacing
the development model artifacts. Phase 8 has not been started.

## Files created

- `backend/app/api/routes/prediction.py`
- `backend/app/ml/opportunity.py`
- `backend/app/schemas/prediction.py`
- `backend/app/services/prediction_service.py`
- `backend/migrations/versions/0004_prediction_result.py`
- `backend/tests/test_prediction.py`
- `frontend/src/components/dashboard/PredictionResults.tsx`
- `frontend/src/lib/predictionFormat.ts`
- `frontend/src/pages/PredictorPage.tsx`
- `frontend/src/services/predictionService.ts`
- `frontend/src/types/prediction.ts`
- `docs/PHASE_7_REPORT.md`

## Files modified

- `backend/app/api/router.py` — register prediction routes.
- `backend/app/models/prediction.py` — nullable JSON result snapshot.
- `backend/tests/conftest.py` — isolated test DB/artifacts/datasets, valid DEBUG,
  and database connection disposal before temporary-storage cleanup.
- `backend/tests/test_migrations.py` — verify an existing prediction survives 0004.
- `frontend/src/App.tsx` — protected predictor route.
- `frontend/src/config/dashboard.ts` — activate predictor navigation.
- `frontend/src/pages/DashboardPage.tsx` — activate prediction action, current-user
  prediction count, correct stale phase copy and distinguish weighted F1 from accuracy.
- `frontend/src/services/apiClient.ts` — preserve structured error details.
- `README.md` — Phase 7 usage, endpoints, scoring and environment notes.
- `CLAUDE.md` — current state and preservation rules.

## Prediction flow

The user searches products in the latest prepared dataset and selects an exact
Phase 5 product identity. The frontend previews the latest per-platform price,
rating, reviews, provenance and observation time, then submits the product key
and the previewed dataset ID.

The backend resolves the active completed model, uses
`training_service.load_pipeline`, verifies its algorithm and saved feature
contract, and selects the latest row for that product on each requested platform.
It uses all 35 saved input columns in their original order: 31 numeric features
and platform, source type, normalized category and normalized brand.

No preprocessing is fitted or recreated. Optional missing values stay NaN for
the saved imputer. Missing feature columns, invalid numeric values, missing or
corrupt artifacts, unsupported request platforms, invalid observation context,
and unusable datasets return explicit errors. A missing platform never receives
an invented class or score. A wholly unsuccessful request creates no history row.

Random Forest probability columns use the estimator's own string class order.
XGBoost integer class IDs map through the existing Phase 6 `CLASSES` definition.
Class probabilities are validated and exposed as uncalibrated model outputs.
Pipelines without `predict_proba` return null confidence/probabilities and no
model-score points.

## Opportunity Score formula

`clip(x)` bounds x to [0, 1]. The score is the sum of weighted components,
rounded to one decimal. Weights are fixed; missing signals are explicit and earn
no points. The API returns each normalized signal, point contribution, weight,
explanation, missing-component list, coverage, and formula version
`observed-opportunity-v1`.

| Component | Maximum points | Normalization |
|---|---:|---|
| Model | 10 | P(improving) + 0.5 × P(stable) |
| Price competitiveness | 20 | clip(1.5 − price / category market median) |
| Rating | 15 | clip(rating / 5) |
| Reviews | 15 | Mean of available clip(log(1 + reviews) / log(10001)) and clip(review momentum / 20) |
| Discount | 10 | clip(discount percentage / 50) |
| Competition | 15 | clip(1 − Phase 5 competition score / 100) |
| Price trend | 15 | clip(0.5 + 10 × price slope / current price) |

Review momentum and price slope are Phase 5 changes per observation, not per day.
The price comparison uses the Phase 5 category peer group. Cheaper prices earn
more competitiveness points but do not imply higher seller margins. Discounts
measure observed activity, not profit. These are documented judgement calls,
not empirically validated estimates of marketplace success.

A positive price plus at least three observed deterministic components covering
40 points is required. Missing components never increase the 10-point ML cap.
Unequal coverage is warned about. Ties use platform name for deterministic display
order and explicitly state that no superiority is implied. A single available
platform is labelled as insufficient for a cross-platform comparison.

## API and persistence

All endpoints require Bearer authentication and respect `API_PREFIX`:

- `GET /ml/prediction-options?q=&limit=50&offset=0`
- `POST /ml/predict`
- `GET /ml/predictions?limit=20&offset=0`
- `GET /ml/predictions/{id}`

Successful predictions reuse the existing Prediction table and existing fields
for user/model references, product input, recommendation, scores, confidence,
factors, model version, timestamp and observations used. Migration 0004 adds one
nullable `result_payload` JSON column for the complete response, including all
platform classes/probabilities, dataset provenance, quality, warnings, score
components, and formula. The insert and response snapshot commit together.

History and detail queries always filter by the authenticated user. Other users'
IDs return 404. Historical quality and warnings come from the saved result,
not the current active model. Legacy rows remain readable in history with an
explicit warning when preserved quality metadata is unavailable.

## Frontend

The existing `/dashboard/predictor` route is now active. It contains searchable,
paginated product selection, observation previews, loading/error/empty states,
ranked result cards, fixed-scale accessible horizontal comparison bars, visible
DEMO/source badges, model accuracy versus majority baseline accuracy, weighted
F1, version, class probabilities, contribution details and recent prediction history.

Warnings are visible in results and each history entry, not hidden in tooltips.
The existing design tokens/components and responsive grid conventions are reused.
No charting dependency, redesign or analytics dashboard was introduced.

## Verification

- Full backend suite: **244 passed**, with five existing dependency-deprecation
  warnings. This includes 38 prediction tests and one additional migration test.
- Frontend `npm.cmd run build`: passed.
- Frontend `npm.cmd run lint`: passed, no warnings after cleanup.
- `git diff --check`: passed.
- Existing active `v2` inference was exercised with actual processed data and
  successful persistence in a temporary copy of the development database.
- A browser smoke test was attempted, but the browser tool reported that no
  browser was available. Visual/browser interaction QA is therefore unverified.

Prediction tests cover real Random Forest and XGBoost pipelines, class order,
null-history compatibility, no-probability estimators, invalid probabilities,
score bounds/determinism/ML cap, partial and absent platforms, persistence,
authentication, user isolation, historical quality preservation, stale observations,
input validation, corrupt/missing/incompatible models and missing/invalid datasets.
The migration test verifies that an existing prediction row survives the update.

## Actual active-model example

This was executed through the prediction service on a temporary database copy;
it did not insert a test prediction into the development database.

- Product: **Acme 20000mAh** (`acme 20000mah|acme|power banks`).
- Model: existing **XGBoost v2**, no retraining.
- Dataset: `bc0dbdd64e9d`, all DEMO; observations dated September 5, 2026, 09:00 UTC.
- Quality: accuracy **33.33%**, weighted F1 **31.87%**, majority accuracy baseline **40.62%**.

| Platform | Opportunity score | Price-direction class | Class probability |
|---|---:|---|---:|
| Croma | 62.6 | declining | 52.0% |
| Alibaba | 54.3 | stable | 63.0% |
| Amazon | — | insufficient_data | — |
| Flipkart | — | insufficient_data | — |

Highest observed opportunity score: Croma, **8.3 points** above Alibaba.
Croma contributions: model 2.473, price 14.027, rating 11.700, reviews 14.397,
discount 5.614, competition 8.738, price trend 5.669. Both scored platforms had
100% component coverage. Croma's declining model class does not prevent its
measured signals from producing the higher heuristic score: ML has only 10% weight.

Every result carried:

> Experimental result: the current model is trained on DEMO data and does not
> outperform the validation baseline. Use this prediction only to demonstrate
> the pipeline. It does not predict actual sales demand.

## Known limitations and preserved Phase 6 concerns

- All current observations/training data are synthetic. Neither model outputs
  nor heuristic rankings are reliable real-market recommendations.
- Probabilities are uncalibrated; heuristic constants have not been validated
  against sales, profit or marketplace success. Signals can be correlated.
- Matching remains strict; the demo fixture has sparse shared identities, so
  many products have only one or two comparable platforms. No fuzzy matching
  or category substitution fabricates wider coverage.
- Phase 7 supports INR and the eight canonical Phase 5 electronics categories.
  It uses stored observations, not hypothetical manually entered products.
- Seven days is an explicit freshness-warning threshold, not a claim that
  younger observations are reliable. A new dataset build does not refresh source
  observations; users must collect/import and rebuild explicitly.
- Local artifacts and processed datasets remain required. Deployment durability
  and object storage are deferred. Migration 0004 runs on the next normal backend
  startup; the development database was not migrated merely for inspection/testing.
- The inactive v1 database/artifact disagreement was preserved, not silently
  repaired. Active v2 was verified. New test storage isolation prevents tests
  from overwriting development artifacts; concurrent training version allocation
  and artifact/database consistency remain pre-existing training concerns.
- Phase 6's timestamp split does not purge boundary-crossing forward labels;
  its evaluation limitations remain. Training architecture was not rewritten.
- A shell exporting `DEBUG=release` still requires a boolean override when
  starting the backend. The test environment now sets a valid boolean.
- Browser visual QA could not run because no browser was available.

No Phase 8 work, scheduled scraping/retraining, or deployment storage changes
were implemented.
