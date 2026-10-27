# Prediction model inventory and submission evidence

Inspected in the final integration sprint. Training implementations are not evidence of trained deployment artifacts. Live Tab 1 activates **no trained model or supplementary forecast**; recommendation ranking uses observations. The retained backend-only live forecast endpoint supplies short persistence estimates for compatibility.

| Family | Implemented research and targets | Shipped artifact | Runtime classification |
|---|---|---|---|
| Rainfall local logistic | `train_rainfall_classification.py`: StandardScaler + logistic regression, strict recent rainfall features, 15-minute event targets with interval ends 15–180 min; comparison with dry/prior/persistence. Requires all three future 5-minute target blocks. | No frozen classifier, scaler or calibration report. | Trained method unavailable. Training scripts remain offline. Historical HTTP no longer refits a neighbor classifier. |
| Rainfall neighbors | `train_rainfall_neighbors.py` and `check_rainfall_sample_rules.py`: local/neighbor features, chronological validation, revised missing-target rules. Former replay fitted 15/30-min methods per request. | No frozen feature/preprocessing/model bundle or neighbor manifest. | Experimental training only; rain probabilities unavailable in live/replay responses. |
| PM2.5 | `train_pm25_multihorizon.py`: regional nonnegative linear prediction versus latest-value persistence; direct 60/120/180-min targets. Exact features: latest PM2.5, lag 1 hour, lag 2 hours, same region, consecutive hourly observations available by origin. Input age <=90 min. | `prediction/results/pm25_multihorizon/backtest_models.json`: 15 region/horizon coefficient records, intercept + 3 coefficients; training cutoff **2026-10-14 00:00 SGT**. | Frozen historical-only experiment. Not a deployment model; no live activation. |
| WBGT | `train_wbgt_multihorizon.py`: latest and 15/30/45/60-min lags, age and diurnal features; direct 15–180-min targets. | No frozen trained artifact or original evaluation reports. | Historical replay persistence; live baseline capped at 15 min. |
| Wind | No verified trained forecast found. | None. | Explicit persistence only; live cap 10 min. Existing neutral wind risk still requires usable input. |
| Live rainfall amount | Latest fresh 5-minute accumulation held constant. Not event probability or expected total rain. | Versioned deterministic method `persistence-v1`. | Experimental baseline only, cap 5 min. |
| Live PM2.5 | Latest fresh regional hourly observation held constant. | `persistence-v1`. | Experimental baseline only, cap 60 min. |
| Catalog rain predictor | Existing `UnavailablePredictor` in live mode; `DemoPredictor` in demo mode. | Synthetic fixtures only. | Live rain probability unavailable; demo mock probabilities are never live forecast evidence. |

The live baseline caps are conservative engineering limits, not validated forecast-skill horizons. They are measured from issue time after the configured freshness check. An older but still fresh input is explicitly timestamped; the estimate is still an assumption of no change. Delayed runs outside these intervals have zero coverage. Unsupported components never yield zero risk.

## Reproducible offline checks

Run `python scripts/evaluate_frozen_forecasts.py` to reproduce [forecast_evaluation.json](forecast_evaluation.json). This command evaluates frozen coefficients and existing baselines without fitting or changing source data. It uses the original research sample constructors and availability rules on `snapshot_20261015`; hashes identify the exact snapshot files and artifact. No external APIs are called.

PM2.5 pooled chronological holdout results across five regions:

| Horizon | Samples | Persistence MAE / RMSE (µg/m³) | Frozen linear MAE / RMSE (µg/m³) |
|---|---:|---:|---:|
| 60 min | 120 | 24.000 / 35.339 | 24.707 / 36.660 |
| 120 min | 115 | 32.678 / 46.335 | 32.541 / 46.561 |
| 180 min | 115 | 42.130 / 56.473 | 40.279 / 54.457 |

Eligible origins begin **14 Oct 2026 09:00 SGT**; last origins are **15 Oct 12:00, 11:00 and 14:00** respectively. Samples are sparse/non-contiguous; the JSON includes exact per-region counts and metrics. The 60-minute model is worse than persistence on both metrics. Longer-horizon results do not establish live reliability or continuous running-window skill.

WBGT persistence only, 30 stations:

| Horizon | Samples | MAE / RMSE (°C) | Eligible origin range (SGT) |
|---|---:|---:|---|
| 15 min | 930 | 0.406 / 0.605 | 14 Oct 11:00 – 15 Oct 09:00 |
| 30 min | 930 | 0.494 / 0.710 | 14 Oct 11:00 – 15 Oct 08:45 |
| 60 min | 990 | 0.550 / 0.782 | 14 Oct 00:30 – 15 Oct 09:15 |

These use the research model's complete lag-history sample set. They are **not** an evaluation of the broader live baseline eligibility set, which requires a fresh latest value rather than all trained-model lags. No trained WBGT superiority is claimed; the live cap remains 15 minutes.

Rain event persistence only, strict complete-block samples across 89 stations:

| Target interval | Samples / rainy samples | Brier | Average precision | Precision / recall |
|---|---:|---:|---:|---:|
| 0–15 min | 890 / 81 | 0.07079 | 0.32582 | 0.70455 / 0.38272 |
| 15–30 min | 712 / 0 | 0 | Unavailable (single class) | Unavailable |

Origins span 14 Oct 10:45 – 15 Oct 08:30 for the first interval, and 14 Oct 11:00 – 15 Oct 03:45 for the second. Zero Brier on an all-dry target set is not evidence of a useful rain-warning model. Outputs are hard occurrence persistence, not calibrated probabilities. No reliability diagram, probabilistic calibration, trained classifier Brier/AUC/AP or defensible trained-vs-baseline comparison is shipped. Live rainfall amount persistence is a different target and has no measured skill claim.

## Availability and scientific limitations

Historical files lack full revision history and historic station geography. Their recorded first-fetch/source-update times support a limited availability filter, not proof that every revision/correction has been reconstructed. Model training cutoffs in the saved JSON are declared metadata, not an independently signed training manifest. The frozen PM2.5 content hash and dataset hashes are recorded by the new evaluator; no coefficients were changed.

Live inference uses `FileRepository.environment_snapshot('live', issue_time)`, preserving revision, first fetch, source update and source-kind semantics. It uses the same catalog source matching as current environmental views and returns issue time, validity interval, model version, horizon/value/unit, input timestamps/revision, station or region, freshness/spatial quality, method, warnings, missing reasons and requested-window coverage. It never consumes historical labels or future observations. Dynamic-route risk remains observation-based; the supplementary live endpoint currently supports catalog routes only.

Missing trained artifacts and preprocessing bundles block rainfall/WBGT deployment. The short, gapped holdout, incomplete snapshot revision history, absent calibration and mixed PM2.5 skill block promotion of trained forecast risk into production ranking. Future work needs frozen/versioned preprocessing and model artifacts, broader chronological evaluation against persistence, calibration where applicable, representative station/season coverage and consistent risk eligibility across the entire requested window. No retraining occurs during route requests.

## Unified historical recommendation workflow

Application workflow is selected by `OUTDOORWISE_APP_MODE`, independently of runtime repository `OUTDOORWISE_DATA_MODE`. Live departs Now; historical departure options are 0/30/60 minutes after **2026-10-15 19:15 SGT**. Models retain their native horizons: PM2.5 60/120/180 minutes from its 19:00 origin; research WBGT targets every 15 minutes. No new horizon, model or training is introduced to match UI options.

The unified historical adapter does not accept the research script's painted intervals as evidence of continuous exposure. Full-window risk and weighted suitability remain unknown; the shared non-environmental fallback and replay-time personal reordering remain available. Existing origin-time policy blocks are preserved. This cannot currently demonstrate validated forecast-based environmental ranking; prediction evidence is embedded within the same route results instead.

Persistence repetitions beyond the existing baseline caps (rainfall 5, wind 10, WBGT 15, PM2.5 60 minutes from replay reference) are marked unavailable rather than extended through arbitrary runs. Frozen direct PM2.5 values may remain available at native targets when complete origin-time features exist. No frozen WBGT/rain classifier is fabricated. Missing PM2.5 artifact is explicitly identified and only the existing recent-observation persistence fallback can apply. Legacy research endpoints retain their interval assumptions for compatibility, outside unified Tab 1.

Prediction Details reports target timestamp, native horizon, method/version, origin/input observed and available times, coverage, and exact-target evaluation labels. Exact target absence remains unavailable; no nearest future observation is substituted. Snapshot CSV local times are parsed as SGT. Signed selected-target error is prediction minus observation, distinct from pooled offline MAE/RMSE. Saved evaluation JSON is read only, never recomputed or trained by the web app. Snapshot revision/geography limitations and the recorded weaker 60-minute PM2.5 performance remain explicit.
