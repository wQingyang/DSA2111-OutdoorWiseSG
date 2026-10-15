# Sprint 2 / 2.1 frontend verification

The dashboard uses the existing form/map layout and vanilla JavaScript. No backend response contract, risk curve, ranking weight, mapping rule, forecasting model or agent implementation was changed.

## Test setup

Python checks use the project's declared development dependencies. Frontend test dependencies are development-only and locked in package-lock.json: jsdom, playwright-core and the already-used Leaflet 1.9.4. Node 26 was used; supported Node versions are declared in package.json. They are not shipped as a new frontend framework.

```bash
npm ci
npm test
# Keep import-time FastAPI initialization away from actual runtime data.
OUTDOORWISE_DATA_ROOT=/tmp/outdoorwise-sprint2-python-check \
MPLCONFIGDIR=/tmp/outdoorwise-sprint2-mpl python -m pytest -q
```

The CI workflow runs both the Python suite and DOM tests. Browser checks require an installed Chrome/Chromium, specified by CHROME_PATH if the platform's default path differs:

```bash
CHROME_PATH=/path/to/chrome \
SCREENSHOT_DIR=/tmp/outdoorwise-ui-screenshots npm run test:browser
```

The browser check starts and stops its own temporary local HTTP server, using synthetic API responses rather than real users or environmental collection. It serves the existing Leaflet library locally and substitutes explicitly labelled offline tiles. It checks real Leaflet geometry/controls, route selection, desktop/mobile overflow, login/profile/register rendering, authenticated refresh ordering, favourites, completed-run feedback and GPX download interaction. It does not establish live OSM/CDN availability or navigation correctness. Authentication response behavior in this test is simulated; actual backend authentication/isolation remains covered by Python tests.

## Actual HTTP smoke check

Use an **isolated data root with a copied catalog**, never a production server or the ingestion worktree. Start a separate live-mode server without collect/watch; empty observations are expected and supported:

```bash
# Prepare /tmp/outdoorwise-ui-http/catalog from data/catalog, then:
OUTDOORWISE_DATA_ROOT=/tmp/outdoorwise-ui-http \
OUTDOORWISE_DATA_MODE=live OUTDOORWISE_AGENT_MODE=demo \
python -m uvicorn outdoorwise.api.app:app --host 127.0.0.1 --port 8769
# In a separate terminal:
BASE_URL=http://127.0.0.1:8769 npm run test:smoke
```

The smoke check executes all dashboard scripts against the actual HTTP backend, derives counts from its response rather than assuming two routes, verifies final ranks, collapsed details, null-score presentation, GPX URLs and SVG fallback. The recommendation endpoint writes its usual run audit JSON only under the isolated root. Stop only the temporary server that you started.

## Fixtures and coverage

`tests/fixtures/frontend_run.json` contains explicitly synthetic twelve-route scenarios built through actual backend contracts. It includes zero risk, unknown rainfall, stale observations, future-unavailable observations, approximate East Coast coverage and a synthetic policy exclusion. Regenerate only when relevant contracts change:

```bash
PYTHONPATH=. python tests/build_frontend_fixture.py
```

The generator parses recorded public response fixtures and uses temporary CSV storage; it neither calls external environmental APIs nor reads actual account/history files. A Python test validates the saved responses against Run and checks personalized order/rank consistency.

The DOM tests cover new recommendation score versus legacy score, valid zero versus null risk, missing/stale/future/approximate assessments, readable route verification warnings, technical timestamps and details, blocked discovery, final personal ranks across load/compare/refresh/chat, visible personal-request failures without silent generic fallback, favourites, run/feedback/GPX actions, partial feedback retry without duplicate runs, catalog decimal-distance validity, distance mismatch/unchanged geometry, and late difficulty-response guards.

## Executed results and screenshots

On 2026-10-15: **104 Python tests passed; 9 DOM tests passed; actual HTTP smoke passed for twelve routes; Chrome desktop/mobile checks passed with zero page errors.** The Python suite retains one upstream Starlette/httpx TestClient deprecation warning. No external live collection was performed. The temporary HTTP server was stopped after verification.

Screenshots are explicitly synthetic fixtures with offline map tiles:

- [Desktop dashboard](screenshots/sprint2/dashboard-desktop.png)
- [Mobile recommendation results](screenshots/sprint2/results-mobile.png)
- [Full mobile dashboard](screenshots/sprint2/dashboard-mobile.png)
- [Login](screenshots/sprint2/login.png)
- [Running Profile](screenshots/sprint2/profile.png)
- [Mobile registration](screenshots/sprint2/register-mobile.png)

The screenshots do not describe current Singapore weather or actual user history. Scoring remains provisional, coverage remains approximate where labelled, and real tile/CDN availability is outside these deterministic checks.

## Sprint 2.1 starting-location verification

On 2026-10-15, the full Python suite passed **109 tests**, and frontend DOM tests passed **21 tests**. Chrome desktop/mobile checks and the real HTTP smoke were rerun and passed; the temporary server used /tmp/outdoorwise-sprint2-1-http-data and was stopped afterward. No collection or shared-environment changes occurred. The earlier Sprint 2 results above remain historical evidence.

The existing browser harness now verifies map click/marker drag and replacement, route-click isolation, presets, native geolocation success and denied permission, manual fallback, personalized Compare/refresh payloads, strict empty results, clear and mobile touch selection. DOM tests additionally verify unavailable/timeout/unsupported geolocation, late callbacks, invalid limits and in-flight location changes. tests/test_starting_location_api.py tests both actual recommendation endpoints against all 12 catalog routes, shared straight-line distance calculation, strict filtering, repeat ordering and invalid coordinates. Browser response fixtures do not pretend to calculate geography.

The dashboard smoke loads location.js alongside the other scripts. Reuse the commands above; approved test installations for this checkout are /tmp/outdoorwise-audit-venv and /tmp/outdoorwise-ui-check (NODE_PATH=/private/tmp/outdoorwise-ui-check/node_modules). For new screenshots set SCREENSHOT_DIR=docs/screenshots/sprint2-1.

See [mode/API/privacy details](STARTING_LOCATION.md), [desktop](screenshots/sprint2-1/location-desktop.png), [mobile controls](screenshots/sprint2-1/location-mobile.png) and [mobile marker](screenshots/sprint2-1/location-map-mobile.png). Screenshots use synthetic API responses/offline tiles. Chrome mobile emulation and location overrides do not establish real-device accuracy or permission UX on every browser.
