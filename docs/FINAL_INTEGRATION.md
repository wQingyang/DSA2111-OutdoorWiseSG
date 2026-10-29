# Final integration and verification

This document describes the supported checkout, not its development chronology.
Use the [README](../README.md) for startup and [architecture](ARCHITECTURE.md) for
module boundaries. Historical research code, coefficients, datasets and saved
evaluation remain protected; this integration does not retrain or alter them.

## Supported behavior

Tab 1 has one form, one **Find Recommended Routes** button and the mode-aware
`/api/route-recommendations` endpoint. `OUTDOORWISE_APP_MODE=live|historical` is
independent of repository `OUTDOORWISE_DATA_MODE=live|demo`; the server determines
the UI mode and a restart is required to change it.

Live supports Now only and reads availability-filtered current observations.
It uses the existing risk, eligibility, ranking and authenticated personalization.
Missing/stale data remains unknown. Duration is not an environmental forecast.
No historical or supplementary forecast service is invoked for Live Tab 1.

Historical Tab 1 uses the fixed **15 Oct 2026, 19:15 SGT** snapshot and departure
options Now/+30/+60. A +60 departure with 30-minute duration requests 20:15–20:45.
Now uses historical observations for numerical departure risk; delayed departures
retain explicit unknown-risk fallback when required inputs are unavailable.
Full-run coverage is assessed separately. Prediction Details preserves native
methods/values, provenance, exact-target evaluation labels and saved pooled metrics.
Ground truth never enters inference. Historical run recording is disabled;
favourites, GPX, location/access constraints and replay-time personalization remain.

Tab 2 retains OpenRouter parsing, coordinate confirmation, manual fallback, ORS
geometry, current-environment risk, personalized difficulty and export in both
application modes. Existing compatibility endpoints are documented in ARCHITECTURE.md.

## Historical availability and scientific limits

Ranges below cover the 12 catalog route matches at the fixed reference. Future
baseline values are research assumptions, not observations or ground truth.

| Indicator | Now, 19:15 | +30, 19:45 | +60, 20:15 | Existing method / blocker |
|---|---|---|---|---|
| Rainfall | 0 mm observations at 19:00 | Unsupported delayed input | Unsupported delayed input | Held 5-minute amount assumption; no frozen classifier or validated delayed-target amount contract |
| WBGT | 25.7–26.7 °C observations at 18:45 | Native persistence point available | Native persistence point available | Existing research targets; no frozen trained WBGT artifact |
| PM2.5 | 95–208 µg/m³ observations at 18:00 | No exact 19:45 target | No exact 20:15 target | Hourly persistence fallback; required 16:00 lag missing in all five regions |
| Wind | 0.566–2.829 m/s observations at 19:04 | Unsupported delayed input | Unsupported delayed input | Held-value assumption lacks validated delayed-target contract; neutral scoring still requires usable wind |

PM2.5 has frozen 60/120/180-minute coefficients, with model origin 19:00 and
native targets 20:00/21:00/22:00. WBGT replay supplies persistence at 15-minute
targets through 180 minutes. Rain probabilities remain unavailable without a frozen
classifier. No new horizons, interpolation, extrapolation or model artifacts are
introduced. Saved 60-minute frozen PM2.5 pooled MAE/RMSE (24.707/36.660 µg/m³) is
worse than persistence (24.000/35.339); those offline metrics are not selected-route
errors. See the [read-only inventory](PREDICTION_MODELS.md) and
[evaluation evidence](forecast_evaluation.json).

The native API slices forecast blocks by overlap, excluding a point ending exactly
at run_start. The departure adapter requests the existing prefix ending at departure
to retrieve that native point without changing its origin or target. It validates
units, source identity, source timestamps and availability before inheriting the
production risk curves, required components and blocking policy. The research proxy's
interval painting and held rain/wind values are not promoted into valid exposure.

The earlier all-unknown results conflated full-run coverage with departure assessment.
Now's observations are usable on all 12 routes; production matching has no failures
at this reference. PM2.5 lacks its 16:00 feature, not its coefficient artifact.
Delayed WBGT supports a heat component, while rain/wind and exact-time PM2.5 remain
unsupported, so overall delayed risk and weighted scores are null. Ranking is
explicitly fallback-based. No differences between +30 and +60 are engineered.

For a 30-minute run, continuous coverage is partial at Now and unavailable at +30/+60;
full-run risk remains unknown in all cases. Snapshot future labels, revision history
and station geography are incomplete. Exact missing ground truth stays unavailable;
no nearby future label or current repository value is substituted.

Valid Now departure scores, independent of run duration:

| Route ID | Departure risk / 100 | Existing eligibility |
|---|---:|---|
| marina_bay | 17.49 | eligible |
| woodlands_waterfront | 12.38 | eligible |
| west_coast | 17.56 | caution |
| east_coast | 17.38 | caution |
| bishan_ang_mo_kio | 18.62 | caution |
| singapore_botanic_gardens | 20.73 | caution |
| macritchie_reservoir | 18.62 | caution |
| pasir_ris_park | 15.62 | caution |
| bedok_reservoir | 16.68 | caution |
| jurong_lake_gardens | 17.21 | caution |
| rail_corridor_bukit_timah | 20.38 | caution |
| punggol_waterway | 10.63 | caution |

The default blocking rules are disabled; eligible/caution labels retain spatial and
component warnings. Configured origin/departure blocks remain exclusions. Shared
risk/ranking formulas, thresholds and route geometries are unchanged.

## Reproduce verification

Install declared Python/Node dependencies, then run:

```bash
.venv/bin/python -m pytest -q
npm test
npm run test:browser
docker compose config --quiet
kubectl kustomize deploy/k8s
git diff --check
```

Python fixtures redirect import-time API initialization and each test's writable
state to temporary storage. Provider responses are recorded or mocked; no actual
users, official collection or request-time fitting are exercised. Frontend DOM tests
cover ordering, missing/stale states, location and account actions. Chromium checks
exercise desktop/mobile layouts, actual Leaflet geometry, synthetic account flows,
and isolated real FastAPI servers in both modes, all historical offsets, GPX and
Tab 2 controls. Tiles/CDN assets are replaced with local fixtures; these checks do
not establish external provider availability. Set `CHROME_PATH` for an installed
Chrome/Chromium and `SCREENSHOT_DIR` for temporary screenshots.

The station experiment has separate [reproduction instructions](../analysis/station_matching/README.md).
Dated real collection evidence is [archived](evidence/collection/README.md), not a claim
that current inputs are fresh.

## Current results

Cleanup baseline: **176 Python tests**, **29 frontend tests**, both browser suites,
Compose configuration, Kubernetes rendering and diff checks passed on 27 Oct 2026.
Post-cleanup checks also passed: **176 Python tests**, **29 frontend tests**, both
Chromium suites including actual Live/Historical servers and the standalone HTTP
smoke, Compose configuration, Kubernetes rendering and `git diff --check`. One
existing Starlette/httpx deprecation warning remains. Relocated comparison/analysis,
isolated CLI checks and research imports pass. All **80 protected-file checksums**
match, including moved scientific evidence; no runtime data or model output changed.
The [cleanup audit](REPOSITORY_CLEANUP.md) records the complete operation inventory.

No model training, real provider collection, Docker image/container execution or
Kubernetes rollout was performed in these checks. Configuration validation is not
deployment acceptance. Remaining work is described in [deployment](../deploy/README.md).

## Existing limitations outside cleanup scope

- Catalog geometry still requires access/visual review. Matching distance and regional coverage are proxies, not direct measurements along every route.
- Generic effort uses non-null environmental values without independently applying the risk assessor's freshness gates. Its attainable range/coverage labels are narrower than the UI's full 1–5 scale. Cleanup does not change that estimator.
- Completed-run predictions and route identifiers are client-reported rather than bound to an immutable server recommendation snapshot. The calibration helper uses input-order residuals; callers are responsible for eligibility.
- Offline personalization replay orders completed runs but does not fully reconstruct feedback availability. Synthetic and real evaluation outputs share destinations, and plotting missing/zero errors needs review before scientific publication. Existing saved evidence and algorithms are unchanged; no new accuracy claim is made.
- CSV/history scans grow with data size; user JSON and SQLite require the documented single-writer storage assumptions. Multi-replica scaling is not supported by adding replicas alone.

## Data and security

Environmental CSV v3, account SQLite and personalization JSON formats remain intact.
Identity is session-derived; simulations are not actual completed runs. Cleanup
checksums compare source datasets, artifacts, evaluation evidence, catalog geometry,
runtime users/observations and relocated experimental CSV/figures against task start.
Pre-existing local modifications are preserved. See the [cleanup audit](REPOSITORY_CLEANUP.md)
for the operation inventory, protected-file comparison and tracking limitations.
