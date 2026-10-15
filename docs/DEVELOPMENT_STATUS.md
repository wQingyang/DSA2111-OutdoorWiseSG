# OutdoorWiseSG development status

## Current status — Sprint 2.1 flexible starting location, 2026-10-15

- Replaced the fixed starting-point selector with one-shot browser location, manual selection on the existing Leaflet map, the three existing approximate presets, and Anywhere/no constraint. A single draggable Start marker and form coordinates track the choice; route clicks do not change it. Clear removes the point. Map failure preserves the other modes.
- Both anonymous and authenticated requests use the existing location={lon,lat} and max_access_distance_km contract. Compare and observation refresh retain the point and personalized endpoint; responses for a changed point/limit are rejected. No backend API or geographic-distance algorithm changed. Anywhere explicitly submits null location/limit. The existing limit is never silently relaxed; empty results explain it. Returned access distances are labelled straight-line, not walking/driving distance.
- Existing Sprint 2 cards, risk-aware ranking, route geometry, accounts, profile, favourites, completed-run feedback and GPX remain functional. No scoring, forecast, ingestion, deployment or dataset changes were made for this sprint. All prior uncommitted changes were preserved; work remains on audit-main with no commits/pushes. The sibling worktree and worker were not accessed.

### Sprint 2.1 verified tests

- Full isolated Python suite: **109 passed**, including five new parameterized API integration cases using the real 12-route catalog for anonymous/authenticated access distances, strict filtering, empty results, clear and coordinate validation. One existing upstream Starlette/httpx deprecation warning remains.
- Frontend DOM suite: **21 passed**. New coverage includes map click/marker replacement/drag, route isolation, presets, single-fix permission/unavailable/timeout errors, unsupported browser, ignored late callbacks, no-location mode, access display/empty states, invalid limits, changed-location response races and personal Compare/refresh persistence.
- Installed Chrome: desktop and mobile checks passed with zero page errors, including native geolocation success/denial, real Leaflet interaction, mobile touch, all existing account/profile/action flows and no horizontal page overflow. Browser APIs use synthetic fixtures/offline tiles; actual distance/filter behavior is covered by FastAPI tests rather than mocked geographic math.
- Actual HTTP smoke: **passed** with 12 catalog routes/12 final cards, collapsed details, null scores, GPX and SVG fallback. Only a temporary live-mode server with empty observations and copied catalog under /tmp/outdoorwise-sprint2-1-http-data was started and stopped; no external collection was run.
- Reused approved isolated Python and frontend test dependencies. Shared Conda, historical observations and training snapshots were untouched.

### Sprint 2.1 files and limits

Frontend: new frontend/location.js and location.css; updated index.html, app.js and results.js. Tests: new test_starting_location_api.py; updated frontend.test.cjs, frontend_browser.cjs and frontend_smoke.cjs. Documentation: STARTING_LOCATION.md, FRONTEND_VERIFICATION.md, README.md, this status and screenshots under docs/screenshots/sprint2-1.

Location selection is page-memory state, retained by observation refresh but reset on full reload. Browser location needs permission/secure context and has device-dependent accuracy; no continuous tracking. Presets are approximate, and no Singapore geofence or travel-time routing was added. Existing Run audit persistence includes chosen coordinates. Mobile evidence uses Chrome emulation, not a physical phone. See [starting-location documentation](STARTING_LOCATION.md) and [desktop](screenshots/sprint2-1/location-desktop.png), [mobile controls](screenshots/sprint2-1/location-mobile.png), [mobile map](screenshots/sprint2-1/location-map-mobile.png) evidence.

## Sprint 2 risk-aware frontend, 2026-10-15

Sprint 2 integrates existing risk-aware responses into the dashboard while preserving the left Plan Your Run form, right Leaflet map, catalog geometry, account/profile pages, favourites, run reporting, personal difficulty and GPX. This section supersedes earlier notes that the frontend still displays the legacy score or redirects anonymous visitors on dashboard load. Backend scoring, weights, mapping, forecasts, agent and deployment implementation are unchanged.

### Verified UI and integration behavior

- Compact route cards display backend final_rank, recommendation_score, environmental risk score/level, rainfall/heat/air components, freshness, confidence, Singapore-local assessment time, readable distance match reasons and important warnings. Scores are labelled with opposite directions: higher recommendation is a better match; higher risk is greater risk. Null risk/weighted scores remain unavailable, never zero or Low Risk. Component risk can remain visible when the overall assessment is incomplete. Stale and future-unavailable selections cannot produce a low-risk summary.
- Environmental Details is a native closed-by-default details section retaining all ten metric rows, measured units/windows, source and station/region, station distance, observation/fetch/source-update timestamps (raw ISO plus SGT), freshness/delivery, matching method, available spatial confidence, original baseline rank/score and full backend risk/ranking warnings. Raw identifiers/diagnostic strings stay out of the default route summary. No technical API data was removed.
- Structured deterministic explanations identify distance mismatch, the highest component risk score and limited/approximate coverage. Distant stations are explicitly described as estimates near the route start, not observations along an entire route. Geometry-review status becomes readable navigation caution. Requested forecast windows are retained but labelled unavailable where the actual response says so; no new forecast or language-model call is introduced.
- A single auth-aware recommendation path is used on initial load, Compare Routes, Refresh observations and after existing assistant interaction. A 401 session check selects the generic endpoint; a valid session selects the personal endpoint and its final ordering. Personal endpoint/network failures are visible and do not silently request anonymous ranking. Generic requests also preserve the selected target difficulty. Stale global personal-rank state is cleared on anonymous renders.
- Blocked routes remain outside the ranked recommendation list and appear in a separate collapsed discovery section, with no recommendation score/rank claim. The map keeps catalog geometry rendering; View Route selects the existing shape. Favourite, Completed Run and GPX actions remain available. Anonymous users can browse and explicitly choose to sign in for saved actions.
- Personal difficulty uses predictions returned with the personalized response, avoiding redundant personal requests. Generic effort still uses the existing endpoint. A render-generation guard prevents old async effort responses from updating new cards or the prediction cache. Run reporting retains available generic/personal predictions; feedback retry reuses the saved run rather than duplicating it.
- Browser verification exposed the existing step=0.01 run-distance input rejecting three-decimal catalog distances such as 4.041 km. It now accepts arbitrary decimal precision without changing geometry or backend values. Account pages explicitly use a single-column auth container rather than inheriting the dashboard grid.

### Sprint 2 tests and evidence

- Full Python suite: **104 passed** (103 existing tests plus validation of the synthetic frontend fixture against actual Run contracts). One existing upstream Starlette/httpx TestClient deprecation warning remains.
- DOM suite: **9 passed** via Node's built-in test runner and jsdom. Coverage includes new/legacy scores, zero/null, stale/future/approximate risk, closed technical details, SGT timestamps, blocked discovery, final personal order across load/compare/refresh/chat, visible personal-request failure without generic fallback, favourite/run/feedback/GPX actions, partial feedback retry, valid decimal distances, distance mismatch, SVG route selection and late difficulty-response protection.
- Actual local FastAPI HTTP smoke: **passed**, with twelve catalog routes/twelve final cards against an isolated empty live runtime; all missing scores remained unavailable, metric details stayed collapsed and GPX URLs/SVG fallback were preserved. No environmental API requests were issued. Only this sprint's temporary port-8769 server was started/stopped; it used /tmp/outdoorwise-sprint2-http-data.
- Headless installed Chrome: **passed** desktop/mobile checks for dashboard, real Leaflet geometry and selection, expandable details, login/profile/register, personal refresh ordering, favourites, completed run and feedback, GPX download, no horizontal page overflow and zero page errors. Screenshots use explicitly labelled synthetic API fixtures and offline map tiles; they are not current weather, real account history or verification of live OSM/CDN availability. See [FRONTEND_VERIFICATION.md](FRONTEND_VERIFICATION.md) for commands and evidence boundaries.
- Existing approved Python test environment was reused. Frontend dev/test dependencies only (jsdom, playwright-core and Leaflet 1.9.4 for offline browser verification) were installed into /tmp/outdoorwise-ui-check. package.json/package-lock.json describe the repeatable test setup; CI now configures Node 26 and runs npm ci/npm test in addition to Python checks. No framework or runtime package was added to the shipped page, and no shared Conda changes were made.

Screenshots: [desktop dashboard](screenshots/sprint2/dashboard-desktop.png), [mobile results](screenshots/sprint2/results-mobile.png), [full mobile dashboard](screenshots/sprint2/dashboard-mobile.png), [login](screenshots/sprint2/login.png), [Running Profile](screenshots/sprint2/profile.png), [mobile registration](screenshots/sprint2/register-mobile.png).

### Sprint 2 changed files

- Frontend: frontend/app.js, index.html, personalization.js, difficulty.js, route-export.js, auth.css; new frontend/results.js and results.css. The original Leaflet/SVG drawing function and route geometry are preserved.
- Tests: updated tests/frontend_smoke.cjs; new tests/frontend.test.cjs, frontend_browser.cjs, build_frontend_fixture.py, test_frontend_contract.py and fixtures/frontend_run.json. The fixture is explicitly synthetic and generated from typed backend contracts/recorded parsers using temporary storage.
- Test setup: package.json, package-lock.json, .gitignore (node_modules), .github/workflows/check.yml.
- Docs/evidence: this file, README.md, a small compatibility note in ENVIRONMENTAL_RISK.md, new FRONTEND_VERIFICATION.md and six screenshots under docs/screenshots/sprint2.

### Remaining limits

Risk curves/weights and coverage bands are still provisional; no along-route sampling or future weather model was introduced. Live map/CDN delivery and production-scale latency are not established by offline browser checks. The existing backend personal-history concurrency, feedback availability and server-side prediction-integrity debt remains. Failed prediction fetches are left unavailable rather than synthesized. Existing uncommitted Sprint 1/user snapshot work was retained; the sibling worktree, ingestion worker, training datasets and historical observation CSVs were untouched. Nothing was committed or pushed.


## Sprint 1 integration hardening (before frontend integration)

This section supersedes the original Sprint 1 confidence cutoff and eligible-before-caution sort policy below. Configurable curves, numerical weights/formulas, authentication, personal calibration, CSV schema and candidate/access filtering are preserved. Existing uncommitted work, dataset replacement and AGENTS.md are preserved; work remains on audit-main with no commits/pushes.

- **Availability versus confidence:** a fresh Mapping V1 station beyond `max_reliable_station_distance_km=5` can now supply an explicit approximate numerical component up to `matching.station_max_distance_km=15`, controlled by `allow_approximate_station_estimates` (default true). Beyond the mapping limit or with unknown mapping/distance the score remains null. Strict mode remains available by setting the flag false. Stale, missing, invalid-contract and future-unavailable observations still cannot supply a score, including neutral wind.
- Components add `estimate_status=supported/approximate/unavailable`. Overall data quality adds `scored_components` and `confidence`, while retaining `reliable_components` for inputs within the confidence gate or supported regional mapping. Completeness counts scorable components, not calibrated measurement reliability. Approximate estimates have very-low confidence and explicit distant-station/route-coverage warnings. Severity remains in risk_level; confidence is independent metadata, and eligibility remains a separately evaluated policy state.
- **Ordering policy:** complete non-blocked eligible/caution routes now share the same descending weighted-score group. Confidence is disclosed, without an arbitrary confidence penalty or automatic eligible-before-caution demotion. Unknown fallback still follows complete assessments; missing values cannot award suitability. Blocks still exclude routes. A rule needs `allow_approximate_estimates=true` plus appropriate supporting policy to trigger from approximate station evidence; an otherwise matching distant estimate produces a warning, not an unsupported automatic block.
- **Personal endpoint:** shared contract-level sort logic is used by both pipeline and personal wrapper. Complete weighted scores already incorporate personal difficulty and never revert to a difficulty-only sort. Unknown personal fallback is performed before Run persistence, with ranking_method=personalized_non_environmental. Both returned recommendation arrays and saved Run use identical final order. final_rank is contiguous after exclusions; personalized_rank aliases that final position.
- **Score/rank meanings:** score and base_recommendation_score remain legacy baseline diagnostics. original_base_rank is the pre-risk/pre-personal candidate index and may have gaps after blocks. recommendation_score is the complete normalized weighted score (or null); final_rank is authoritative final position. personalized_score remains negative mismatch for compatibility and only governs unknown personal fallback. OpenAPI field descriptions and ENVIRONMENTAL_RISK.md document these meanings. Recommendation risk_confidence summarizes the route risk quality without duplicating components.

### Hardening verification

The existing isolated `/tmp/outdoorwise-audit-venv` was reused; no dependencies/shared environments were changed. Full suite: **103 passed**, including all 90 Sprint 1 cases and 13 new parameterized regressions. The original spatial-cutoff test now explicitly selects strict mode and keeps its existing assertions; new tests cover default approximate mode, the 15 km cap, temporal unavailability, caution-versus-eligible comparison, authorized/unauthorized approximate blocks, and personalized weighted/fallback ordering. Real IDs east_coast/west_coast and recorded Mapping V1 distances 5.193 km and 1.816 km are used with explicitly synthetic weather. All twelve real catalog IDs participate in endpoint tests. Blocked candidates are excluded and final ranks remain contiguous. One existing upstream Starlette/httpx TestClient deprecation warning remains.

Command (temporary default data root also protects import-time API initialization):

```bash
OUTDOORWISE_DATA_ROOT=/tmp/outdoorwise-sprint-test-default \
MPLCONFIGDIR=/tmp/outdoorwise-sprint-mpl \
/tmp/outdoorwise-audit-venv/bin/python -m pytest -q
```

A separate manual integration check copied only this worktree's environmental CSVs, CSV metadata and twelve-route catalog to a temporary data root. It did not copy accounts or personal history, initialize repositories on source runtime, fetch APIs, alter timestamps, read the sibling worktree, or operate a worker. Source file SHA-256 hashes before/after were identical. The copied runtime contained 260,015 eligible live observation records at inspection. Historical replay used existing revision/availability rules:

| Evaluation | Result |
| --- | --- |
| Latest snapshot fetch time: 2026-10-15 19:07:03 +08:00 | All 12 overall scores remain unknown: rainfall, heat and air-quality components are stale. Only fresher wind does not establish complete current conditions. |
| Historically aligned time: 2026-10-14 21:52:45 +08:00 (minimum of latest available fetch times across sources) | Strict cutoff: 11 complete; hardened approximation: 12 complete. Five eligible, seven caution; confidence moderate=5, low=6, very_low=1. |
| East Coast at historical time | Risk 12.92, caution/very_low confidence; wind source distance 5.193 km explicitly approximate. This is historical replay, not a current-weather claim. |
| Generic 4 km historical request, no starting location | Final top three: Marina Bay 80.99, West Coast 78.67, Bishan–Ang Mo Kio 78.27. West Coast is caution yet can rank ahead of eligible routes using the weighted score. |
| Same copied environments evaluated one day later | Zero complete scores; historical freshness was not preserved as permanently current. |

Machine output and replay helper are local temporary artifacts `/tmp/outdoorwise-hardening-validation.json` and `/tmp/outdoorwise-hardening-validate.py`; key evidence is retained above. Local snapshot history is not refreshed or rewritten to manufacture current data.

### Hardening changed files and limits

Changed in this pass: `config/environment.toml`; `outdoorwise/contracts/risk.py` and `models.py`; `outdoorwise/modules/risk.py`, `risk_policy.py`, `risk_ranking.py`; `outdoorwise/pipeline/runner.py`; `outdoorwise/personalization/ranking.py`; `tests/test_environmental_risk.py`; `docs/ENVIRONMENTAL_RISK.md`; this status file; and README's suite count. No frontend, ingestion/storage adapter, historical dataset, worker, forecasting, agent or deployment files were changed in this pass.

Approximation is a documented engineering policy, not proof that a distant station represents the route. Scores and spatial bands remain uncalibrated, the current local runtime remains temporally incomplete, and the frontend still displays legacy score. Pre-existing personal-history concurrency/feedback-availability debt remains out of scope. There is no new medical or safety claim, enabled default block, future-weather model or along-route sampling.


## Initial Sprint 1 implementation (before hardening)

Sprint 1 implements **observation-based environmental risk, separate eligibility policy, and risk-aware recommendation ranking**. The original audit below is retained as a dated baseline; its statements that risk is unavailable, ranking is distance-only, and the full suite is dependency-blocked are superseded by this section. Forecasting, route sampling V2 and frontend work remain unimplemented in this sprint.

- `EnvironmentalRiskAssessor` scores rainfall, WBGT/category fallback, PM2.5/PSI fallback and wind. Component scores, freshness, spatial quality, completeness, provenance references, warnings and eligibility are returned in `Run.risks`. Four usable components are required for an overall score; null is never converted into zero or silently renormalized. Source freshness is recalculated at evaluation time, including future availability checks.
- Risk defaults: rainfall 35%, heat 35%, air quality 25%, wind 5%. Wind is neutral only with a usable measurement; it remains unknown when missing. Heat/air alternatives are never added together. Curves and quality bands are provisional; WBGT category boundaries are sourced to MSS/NEA. All assumptions, formulas and references are in [ENVIRONMENTAL_RISK.md](ENVIRONMENTAL_RISK.md).
- `RiskPolicy` returns eligible/caution/unknown/blocked. No blocking rules are enabled by default. Enabled numeric rules require a policy source and reason, and usable observations; source applicability still requires operator review. Blocked routes are removed from generic and personalized recommendations while retained in catalog/risk results.
- `RiskAwareRanking` runs after existing distance/access candidate generation. Complete groups use 45% environmental suitability + 25% relative distance match + 15% accessibility + 15% difficulty match. Missing location receives the same disclosed neutral accessibility across candidates. Anonymous requests use the existing generic difficulty estimator; authenticated requests supply existing personal calibration from the same environment snapshot.
- Eligibility precedes score. Unknown groups have a null weighted score and explicit legacy fallback; the authenticated fallback retains difficulty-mismatch ordering. Personal preference cannot bypass a block or reintroduce excluded candidates. Original baseline scores and ranks are preserved; `recommendation_score` is the new score. Distances report absolute/relative mismatch and configurable warnings (>30% default), with a Run warning if no surviving route is close.
- HTTP changes are additive: existing endpoint paths/fields, auth and personal response wrapper remain. Generic requests can optionally set `target_difficulty` (default 3). Risk summaries/ranking metadata are added to recommendations; full risk data is stored once per route in `Run.risks`. Prediction outputs explicitly distinguish forecast available/unavailable; risk mode remains current_observation. Forecast horizon and run duration are preserved without inventing future values.
- Environmental CSV schema v3, ingestion, history, user storage and route geometry are unchanged. No frontend, agent, Docker, Kubernetes, forecasting model or dataset changes were made by Sprint 1. Existing user-managed snapshot deletions/new snapshot, untracked AGENTS.md and prior status document were preserved. Work stayed on `audit-main`; nothing was committed or pushed. The sibling directory and active worker were not accessed during implementation.

### Sprint 1 verification

The user approved installation of declared project/test dependencies only into `/tmp/outdoorwise-audit-venv`. The shared Conda environment was not modified. Sandbox DNS blocked the initial download; the approved escalated download succeeded. Resolved major versions: Python 3.13, FastAPI 0.143.1, Pydantic 2.14.1, httpx 0.28.1, pytest 9.1.1, matplotlib 3.11.2.

```bash
OUTDOORWISE_DATA_ROOT=/tmp/outdoorwise-sprint-test-default \
MPLCONFIGDIR=/tmp/outdoorwise-sprint-mpl \
/tmp/outdoorwise-audit-venv/bin/python -m pytest -q
```

**90 tests passed**: all 46 pre-existing cases plus 44 new parameterized cases. The only warning is a Starlette TestClient/httpx deprecation from the newly resolved dependencies; no extra undeclared dependency was installed to suppress it. Tests use temporary roots, synthetic typed observations and recorded fixtures; no external environmental collection, real user-history mutation or production-worker operation was run. `git diff --check` passed. Full browser, real live thresholds, forecast accuracy and deployment are not claimed verified.

New cases cover interpolation boundaries; zero versus missing; numeric/category heat; PM2.5/PSI precedence and aggregation windows; stale/future/missing timestamps; source contract checks; spatial bands; neutral/missing wind; weights/config validation; default-disabled and explicitly supported synthetic blocking policies; changed ranking; original score/rank preservation; unknown/anonymous fallback; personal integration and block precedence; access filtering; distance mismatch/no-match warnings; determinism; unavailable forecasts; and API field/GPX/profile compatibility. One new API fixture initially failed because its fixed timestamp was not fresh at the actual request time; it was corrected to generate fresh synthetic observations. No existing assertions were relaxed.

Synthetic comparison (target 4 km, both routes 4 km, no location, difficulty/target=3): route a with rain=10/WBGT=35/PM2.5=350 moves from tied legacy rank 1/score 100 to risk 95/new rank 2/score 49.75; route b with rain=0/WBGT=26/PM2.5=0 moves from legacy rank 2/score 100 to risk 0/new rank 1/score 92.50. This is a controlled fixture, not real weather or accuracy evidence.

### Remaining priorities after Sprint 1

1. Review/calibrate provisional curves, coverage gates and weights using appropriate environmental/pilot evidence; define any population-specific blocking policy before enabling it.
2. A later frontend sprint should display recommendation_score, eligibility and structured risk warnings. The unchanged UI still shows legacy score; all route-level mismatch reasons are included for compatibility.
3. Preserve unknown fallback but validate user expectations around eligible/caution priority and categorical/regional approximations. Neither eligibility nor a low score guarantees safety along a route.
4. The pre-existing JSON-history concurrency, feedback-time leakage, client-reported prediction integrity and generic difficulty stale-data issues in the audit remain outside Sprint 1. Difficulty behavior was preserved, not redesigned.
5. Build valid forecast labels/models and future-duration risk modeling separately; review all route geometries and evaluate along-route sampling before making more precise spatial claims.
6. Keep expanded browser smoke verification, performance/scalability work, source availability and Docker/provider verification on the backlog. PROJECT_CONTEXT remains absent from this checkout; no sibling read was attempted in this sprint.

### Sprint 1 changed files

- Configuration/composition: `config/environment.toml`, `outdoorwise/config.py`, `outdoorwise/bootstrap.py`.
- Additive contracts: `outdoorwise/contracts/risk.py` (new), `outdoorwise/contracts/environment.py`, `outdoorwise/contracts/models.py`.
- Scoring/policy/ranking: `outdoorwise/modules/risk.py`, `outdoorwise/modules/risk_policy.py` (new), `outdoorwise/modules/risk_ranking.py` (new), `outdoorwise/modules/recommender.py`, `outdoorwise/pipeline/runner.py`.
- Existing personalization integration: `outdoorwise/personalization/router.py`, `outdoorwise/personalization/ranking.py`.
- Tests: `tests/test_environmental_risk.py` (new, 44 parameterized cases).
- Documentation: `README.md`, `docs/ARCHITECTURE.md`, `docs/PERSONALIZATION.md`, `docs/TEAM_HANDOFF.md`, `docs/ENVIRONMENTAL_RISK.md` (new), and this pre-existing uncommitted status document (updated with Sprint 1 results, retaining the earlier audit).

## Pre-sprint audit (historical baseline)


Last audited: 2026-10-15 (Asia/Singapore). Source of truth: the code in `outdoorwise-main` at `d8ad8f9cfb31b5b8d79b00d5f6023b931be3059e`, branch `audit-main`.

This is persistent development memory, not a claim that proposed features are complete. Update verified behavior, test results, and outstanding gaps when they change. Application code was not changed during initialization of this file.

## Audit scope and reference limitations

Inspected README, CONTRIBUTING, all Python modules and tests, frontend HTML/JS/CSS, configuration and deployment files, module templates, documentation/schema/evidence files, route GeoJSON, recorded API fixtures, dataset and runtime CSV contents, and recent Git history. Large CSVs were inspected programmatically for counts, fields, metrics, provenance, and time ranges rather than reproduced as text. No account database contents or user credentials were read.

Neither `AGENTS.md` nor `docs/PROJECT_CONTEXT.md` exists in this checkout. At the user's direction, `../outdoorwise-demo/AGENTS.md` was read as reference documentation only. `../outdoorwise-demo/docs/PROJECT_CONTEXT.md` is also absent. No sibling files were modified. Therefore a direct comparison against PROJECT_CONTEXT is **blocked by the missing document**; do not invent its requirements. The design comparison below uses this checkout's `ARCHITECTURE.md`, `TEAM_HANDOFF.md`, `PERSONALIZATION.md`, and the supplied sibling AGENTS reference, checked against actual code.

Git was clean before the audit. Relevant history:

| Commit | Date | Change |
| --- | --- | --- |
| `d8ad8f9` | 2026-10-14 | Added historical environmental CSV snapshot for future training |
| `646f4b5`, `7a4d98b` | 2026-10-14 | Merged/updated expanded-route README |
| `a6ca7b5`, `6b8c324`, `05b45cf` | 2026-10-14 | Added ten routes and adjusted Python tests |
| `e9c2b4f` | 2026-10-11 | Merged personalization work, including accounts/difficulty/export/evaluation |
| `d06022a` | 2026-10-07 | Added continuous live collection |

No branches were switched, repositories merged, commits created, or changes pushed.

## Architecture and actual data flow

The application is a synchronous Python/FastAPI service serving a plain JavaScript frontend. `bootstrap.py` composes the environmental pipeline; API setup separately composes accounts and personalization. There are three distinct storage systems: environmental CSVs, account/session SQLite, and personalization JSON. Do not describe all persistence as CSV or assume a production database exists.

```text
config/environment.toml + Settings/environment variables
  -> eight independent data.gov.sg collectors
  -> validated CollectionBatch / EnvironmentObservation / Location
  -> Pipeline.refresh -> FileRepository.ingest
  -> category observation CSVs + revision CSVs + locations + ingestion logs
  -> RouteEnvironmentService (mode + query time + route geometry + region config)
  -> route mappings and latest summaries / typed RouteEnvironment
  -> Pipeline.run: rainfall Conditions -> predictor; environments -> risk assessor
  -> BaselineRecommender -> validated Run + JSON audit/prediction snapshots
  -> FastAPI JSON endpoints -> frontend route cards, tables, map and assistant

authenticated session (accounts.sqlite3)
  -> user-scoped completed runs / favourites / feedback (personalization/*.json)
  -> derived profile -> generic difficulty + personal calibration
  -> target-difficulty reranking of the existing recommendation candidates
```

1. **Collect:** `collect`, explicit `/api/refresh`, or the separately started live-only `watch` worker fetch rainfall, wind speed/direction, temperature, humidity, PM2.5, PSI/PM10, and official WBGT/heat stress. Eight endpoints produce ten metrics. Collectors validate source types/units, normalize wind knots to m/s, and preserve source observation/update/fetch times. Transport has bounded retries, timeouts, and inter-source spacing. Individual source failures are logged and do not replace live data with demo values.
2. **Persist:** `storage/repository.py` is the environmental CSV owner. Weather, air-quality and heat-stress each have observation and revision tables. Keys include source, location, observation instant, metric, aggregation window and live/demo kind. Deduplication refreshes fetch time; corrections create revisions. Thread/process locks, temporary-file replacement, and a pending journal serialize/recover writes. Multi-file updates are recoverable, not one filesystem-wide atomic transaction. CSV times are Asia/Singapore local seconds without suffixes; internal/HTTP times are aware.
3. **Match:** The service reconstructs eligible observations as of the query time, including first-fetch and source-update availability. Each station metric independently uses the route's first coordinate and nearest available station, preferring fresh readings, with a 15 km cutoff. PM2.5/PSI/PM10 use curated TOML regions. It labels fresh/stale/missing and live/cache/demo/unavailable. `get_route_environment` recalculates rather than blindly trusting the materialized latest CSV. Historical station metadata is not fully versioned.
4. **Recommend:** `Pipeline.run` projects rainfall into the compatibility `Conditions` input. The live predictor returns unavailable probabilities; risk assessment returns unavailable reasons. The baseline score is `100 - 10*distance_difference - 2*access_distance - 50*rain_probability`, with the latter two terms only when available. The only exclusion is the optional maximum straight-line access limit. **Observed rainfall does not directly affect this score.** In live mode no rain forecast exists, so score depends on distance and optional access distance. Risk outputs and other environmental metrics are not passed into the baseline recommender.
5. **Personalize:** Generic difficulty uses route length, rainfall and the WBGT/category/temperature-humidity fallback. Personal difficulty uses median historical residuals, shrinkage and comfortable distance. Authenticated recommendations reorder only baseline candidates by absolute target mismatch and original rank. Favourites do not influence ranking. Accounts use scrypt and hashed server-side session tokens with HttpOnly cookies. Owner dependencies reject another user's ID.
6. **Present:** `/api/recommendations` returns the full Run; `/api/me/recommendations` adds personal ordering. Vanilla JS renders cards, ten-metric tables and provenance, Leaflet/OSM routes with SVG fallback, history/forms and GPX links. Difficulty scripts make separate per-route requests. The assistant uses an allowlisted tool registry; default mode is a fixed sequence. LLM mode uses a configured chat-completions provider. It cannot fetch environmental APIs through its tools; some tools run the pipeline and save local snapshots.

## Implemented functionality

| Area | Verified code behavior / evidence |
| --- | --- |
| Environmental ingestion | Eight live parsers with recorded official fixtures; ten typed metrics; canonical units/windows; missing values retained |
| CSV persistence/history | Category storage, revisions, deduplication, timezone encoding, locking, transaction replay, ingestion records |
| Collection operations | CLI collect/due/watch/status; persisted cooldowns; exclusive continuous-worker lease; SIGINT/SIGTERM handling |
| Route catalog | Twelve CSV routes and individual LineStrings; combined GeoJSON has matching IDs; all twelve have `candidate_requires_visual_review` status |
| Environment API | Current/historical route environment with source matching, distance, timestamps and freshness/delivery labels |
| Baseline recommendation | Distance/access scoring, optional access exclusion, deterministic ordering and validated output IDs |
| Accounts | Register/login/logout/me/availability, UUID identity, case-insensitive usernames, scrypt, expiring server sessions |
| Running history | User-isolated runs, derived pace, favourites, linked 1–5 feedback/tags/comments, derived profile |
| Difficulty/personal ranking | Rule-based generic effort estimate, historical residual calibration, cold start, candidate-preserving target mismatch ranking |
| GPX | GeoJSON ordering and longitude/latitude conversion preserved; export does not generate new geometry |
| Evaluation tooling | Replay, aggregate/per-user metrics, synthetic fixtures, CSV/JSON reports and matplotlib figures |
| UI/assistant | Map/cards/forms/profile/auth pages, metric provenance, fixed demo agent and implemented provider tool loop |
| Delivery scaffolding | Dockerfile, app/collector Compose services sharing runtime, pytest GitHub Actions workflow |

“Implemented” here means present and traced in code. Only the executed subset below has current passing-test evidence; README's full-suite claim is not independent verification.

## Partial or missing functionality

- **Forecasting:** `UnavailablePredictor` in live mode; demo probabilities are hardcoded for the original two routes, with null probabilities for ten newer routes. No training pipeline, future-rain labels, saved trained model, forecast validation or backfill implementation exists. A historical data snapshot alone does not implement a forecasting model.
- **Environmental risk and suitability:** `UnavailableRiskAssessor` is explicit. No comprehensive risk model or environmental exclusion policy is connected. Official heat stress is an observation, not that model. Baseline ranking does not exclude high heat, pollution, stale measurements, missing measurements or unreviewed geometry.
- **Spatial accuracy:** Start-point station matching and configured air-quality regions only; no along-route sampling, polygon containment, elevation/gradient, shade, surface, facilities or travel-time routing. Routes are candidates, not validated navigation paths. No checked-in route-generation workflow was found.
- **Personalization validity:** Formulas and UI exist, but no verified real-user accuracy evidence. The temporal/data-integrity issues below limit stronger claims.
- **Operations:** No PostgreSQL adapter, Kubernetes manifests, hosted worker, automatic browser polling or production monitoring/backfill. Docker and real LLM/provider calls were not validated in this audit.

## Data inventory and reproducibility

Committed `data/datasets/snapshot_20261014/` contains **259,853 observation rows**: 225,823 weather, 2,410 air-quality and 31,620 heat-stress. It also includes 201 locations and 120 route/metric mappings. Observations span 2026-10-05 through 2026-10-14 in stored Singapore time; the latest weather observation is 2026-10-14 21:59. Rows are labelled live; that label and prior collection evidence are not a new live API verification.

The snapshot is not automatically read by `build_pipeline`. It contains neither ingestion logs nor revision tables; merely copying its current observations into runtime would not establish the revision history required by `environment_snapshot`. It lacks a dataset manifest/extraction procedure and forecast labels. Do not assume historical availability can be reconstructed completely from it.

This workstation also has ignored `data/runtime` data: the same current-observation counts, 120 summary rows, 9,309 ingestion records, and 7,905 air-quality revision rows (weather/heat revision counts equal their current counts at inspection). Local runtime includes an accounts database and saved pipeline JSON. These are local state, not part of a clean clone; audit tests used temporary data roots. No running/healthy worker was inferred from lock-file presence. Existing observations are old enough to be stale at audit time.

Only `.gitkeep` is tracked under runtime. README's statement that the package includes verified live CSVs needs qualification: the tracked snapshot is separate from the runtime directory used by default. Historical docs/example_run.json contain two routes and earlier 234/468/702-observation evidence; those are dated artifacts, not current inventory or new test results.

## Technical debt and correctness findings

These are code-inspection findings unless a direct probe/test is specifically noted. They have not been fixed.

1. **Personalization writes can lose updates.** `PersonalizationRepository` has an instance-local RLock; API dependencies construct new instances per request. Concurrent requests or processes can read the same JSON and replace each other's updates, despite atomic replacement. It has no cross-instance/process equivalent of the CSV repository's locking.
2. **Replay can leak late feedback.** `evaluation/personalization.py` selects prior runs by `completed_at` but does not require prior feedback `created_at` to precede the evaluated prediction/run. The tests actually use feedback created much later than the historical runs. Strictly earlier run timestamps alone do not guarantee feedback was available at prediction time. The deployed predictor also takes the last ten residuals in persistence order rather than explicitly sorting by completion time; future-dated runs are not rejected or filtered.
3. **Difficulty ignores freshness and misstates coverage.** `GenericDifficultyEstimator` accepts non-null stale values without checking `state`. A direct saturated-input probe with stale WBGT/rainfall returned 3.85/5. The maximum generic score is 3.85, so “Very hard” above 4.2 is unreachable. Its `full` coverage threshold of four features is unreachable on the normal WBGT or heat-category path (distance + heat + rainfall = three), even with complete observations.
4. **Prediction/history integrity is weak.** Run creation accepts client-supplied generic/personal predictions without tying them to an immutable recommendation snapshot. Arbitrary route IDs and future completion times are accepted; favourites also accept arbitrary IDs. Repeated feedback for the same run is allowed; dictionary consumers select the last stored feedback without an explicit revision policy. Run and feedback saves are separate requests, so retry after partial failure can duplicate a run.
5. **Anonymous frontend flow conflicts with the public API.** `personalization.js` redirects a visitor to login when `/api/auth/me` reports Authentication required, although generic endpoints are public. This is source-level evidence; not browser-reproduced during this audit.
6. **Frontend personal ordering can become misleading.** Initial load, refresh and chat render generic runs. `window.personalizedRanking` can survive refresh/chat and annotate a generic order with old personal ranks; broad fallback catches can silently hide personal-endpoint failures. Difficulty requests are asynchronous and unversioned, so repeated renders can attach late results or save a run before prediction fetches finish.
7. **Frontend regression check is outdated.** `tests/frontend_smoke.cjs` hardcodes two cards, twenty metric rows and two fallback SVGs. The current unfiltered catalog has twelve cards/120 metric rows; a fresh clone can also legitimately show missing observations. It evaluates only app.js, omitting auth/personalization/difficulty/export interactions, and is not run by CI.
8. **Storage/read costs grow with history.** CSV ingestion loads/rewrites all observation/revision groups; environment reads load all histories and calculate all routes even for one route. Personal recommendation/difficulty requests repeat this work per route. JSON user histories also scan whole files. No pagination/retention/partitioning or measured latency budget is implemented.
9. **Evaluation output provenance needs correction.** `--synthetic` isolates input fixtures, but aggregate reports/figures are written to the same runtime/evaluation destinations as real results, without a synthetic marker in the result object. Plotting converts missing MAE to zero, zero learning-curve MAE to NaN, and stacks generic/personal per-user errors under an improvement filename. These can misrepresent evidence despite tests confirming file creation.
10. **Configuration, docs and packaging drift.** UI copy and pipeline geometry warnings still refer to two routes. README's description of rainfall ranking overstates direct use of observations. requirements.lock.txt omits matplotlib and is unused by CI/Docker, which resolve broad pyproject ranges; frontend jsdom has no checked-in dependency manifest. Environmental composition is centralized, but personalization/account construction is separate. The AST boundary test covers selected original packages and skips relative imports, so it does not enforce the whole application's dependency structure. Importing `api.app` constructs the default pipeline and can initialize default runtime during test collection.

## Verification performed

| Check | Current result |
| --- | --- |
| `python -m pytest -q` | Exit 2: 11 test-module collection errors, all rooted in missing `fastapi` in `/opt/anaconda3` Python 3.13. No full-suite test result obtained. |
| `python -m pytest -q tests/test_architecture.py tests/test_storage_layout.py tests/test_worker.py` | **10 passed in 1.77s**, including subprocess worker shutdown/lease checks and CSV timestamp/recovery behavior. |
| Catalog/data inspection | Twelve IDs agree between CSV and combined GeoJSON; all routes remain candidates. Snapshot/runtime row counts and time ranges inspected. |
| Direct generic-difficulty probe | Stale values were used; saturated score returned 3.85 and coverage `partial`. |
| Full browser/DOM, fresh external APIs, real LLM, Docker | Not executed. Outdated smoke assumptions identified by reading source, not recorded as a newly executed failure. |

There are 46 Python `test_*` functions in the checked-in suite, matching README's count; only ten were executed successfully here. No assertion failure was observed in those ten. The remaining suite is **environment-blocked**, not proven passing or failing at assertion level. A temporary venv was created under `/tmp`; dependency download failed under sandbox DNS restrictions and the escalated retry was interrupted without completing installation. Do not treat it as installed or dependencies as verified.

Existing tests cover parser fixtures, revisions/as-of, failure isolation/cache/retries, worker lifecycle, basic account isolation, profiles, heat hierarchy, personal ranking, GPX and evaluation outputs. They do not establish concurrent personalization correctness, feedback availability at replay time, stale-input difficulty behavior, full twelve-route UI behavior, real predictive accuracy or deployment readiness.

## Gaps against available design references

| Documented intent / invariant | Actual implementation and gap |
| --- | --- |
| Current implementation overrides planned design | Applied here; PROJECT_CONTEXT comparison remains pending because the file is absent in both locations |
| Environmental ingestion -> shared structured reader -> modules | Implemented, with current ten-metric reader and CSV v3 semantics |
| Trained 30/60-minute forecasts and comprehensive risk modules | Interfaces/stubs only; data snapshot does not fill these gaps |
| Base recommender owns environmental/feasibility filtering; personalization only reranks | Candidate-preserving reranking is implemented; base environmental filtering itself is absent |
| Preserve anonymous generic and authenticated personal flows | API separation exists; automatic UI login redirect and mixed render paths conflict with that intent |
| Use only eligible past history/feedback | Partial: chronological run filtering exists in evaluation, but feedback availability and online history ordering/eligibility are incomplete |
| Recent ten residuals and trustworthy prediction snapshots | Last ten stored residuals, client-reported predictions, no immutable run-time prediction linkage |
| Synthetic evidence isolated and labelled | Inputs isolated; report output locations and metadata do not reliably separate real/synthetic evidence |
| Future PostgreSQL/container scalability | Repository port and Compose exist; PostgreSQL and multi-writer personalization guarantees do not |
| Routes usable offline and expandable | Static twelve-route catalog works without live OSM generation; geometry approval and expanded demo/UI verification remain incomplete |

## Prioritized development plan

Implementation is future work; this audit authorizes no application edits.

1. **P0 — Establish a reproducible baseline and recover design context.** Integration owner: provision declared dependencies in an isolated environment, execute all 46 tests, record actual versions/results, then modernize the frontend smoke setup to derive counts from catalog/candidates and support missing data. Obtain the intended PROJECT_CONTEXT before asserting alignment. Exit: repeatable full Python and expanded UI checks with explicit current evidence.
2. **P0 — Protect personal history correctness.** Accounts/personalization owner: agree on shared locking or transactional persistence; enforce eligible timestamps, chronological history ordering, feedback availability and a duplicate/revision policy; bind saved predictions to server evidence. Coordinate unknown-route validation because current tests accept arbitrary IDs. Exit: concurrent-request, backdated-run, future-dated-run and late-feedback regression cases pass without changing user isolation or candidate sets.
3. **P1 — Make user-facing behavior consistent.** Frontend/difficulty owners: retain anonymous access, use the intended recommendation path across load/compare/refresh/chat, clear obsolete ranking state, guard async prediction rendering/save timing, expose freshness in difficulty, and review score range/coverage/explanations. Exit: browser checks for anonymous and authenticated flows across twelve routes, with stale/missing inputs handled explicitly.
4. **P1 — Define and implement environmental suitability.** Risk/recommendation owner: agree on evidence-based semantics, thresholds, missing/stale behavior and how risk reaches ranking/filtering; preserve separate effort and risk concepts. Exit: deterministic acceptance/exclusion cases, explained provenance and candidate-preserving personal reranking. Do not advertise current ranking as environmental screening before this is connected.
5. **P1 — Turn observations into a valid forecast dataset and model.** Ingestion/prediction owners: document snapshot provenance, label future rain at 30/60 minutes, define feature/label time availability, backfill needs, time-based splits and baseline evaluation; implement/inject a trained predictor only after validation. Exit: held-out metrics and model version, no availability leakage, correct null/unavailable behavior and live-mode mock rejection.
6. **P2 — Validate routes and spatial representation.** Route owner: visually review all twelve candidates, verify lengths/access/continuity and region assignments; assess along-route sampling against start-point matching. Exit: recorded review status and geospatial regression checks; no invented facilities/elevation.
7. **P2 — Harden performance, evidence and delivery.** Integration/evaluation owners: benchmark current history-sized requests and ingest; reduce repeated full scans, define durable/shared storage before scaling, fix real/synthetic report separation/plots, align dependency lock and CI, verify Docker and an optional real provider. Exit: reproducible evidence, latency/storage measurements and documented operating limits.

Preserve stable route IDs, timezone/unit/null/provenance semantics, environmental revision history, account SQLite and user identity, separate personal JSON history, and original candidate-set ranking semantics unless a coordinated change explicitly revises them. Future work should read this file alongside the actual touched modules and tests; this dated audit is not a substitute for inspecting later code.
