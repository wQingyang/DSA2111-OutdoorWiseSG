# Actual Verification — 2026-10-05

A single default-live `python -m outdoorwise.cli collect` ran in the existing project from 2026-10-05 03:38:16 to 03:39:52 UTC (11:38 to 11:39 in Singapore). All eight sources succeeded on their first request and inserted **234 live observations**. No source fell back to mock data. Counts and timestamps are recorded in verification.json and data/runtime/ingestion_runs.csv.

| Source | Received / inserted |
|---|---:|
| Rainfall | 89 |
| Wind speed | 17 |
| Wind direction | 17 |
| Temperature | 18 |
| Humidity | 18 |
| PM2.5 | 5 |
| PSI + PM10 | 10 |
| WBGT + heat stress | 60 |

The two routes produced 20 latest metric summaries and 20 source mappings. All ten metrics had real observations. The complete pipeline response is recorded in example_run.json. The matched sources were:

| Metric | Marina Bay | Woodlands Waterfront |
|---|---|---|
| Rainfall | S119 | S104 |
| Wind speed / direction | S108 | S104 |
| Temperature / humidity | S111 | S104 |
| PM2.5 / PSI / PM10 | south | north |
| WBGT / heat stress | S144 (Hong Lim Park) | S125 |

## Tests and Frontend

`python -m pytest -q` passed 12 tests. Coverage includes recorded official response parsing, changed-unit rejection, deduplication, revisions, equivalent timezone instants, historical as_of queries, missing and stale observations, failure isolation, live cache delivery, retries, single-writer locking, journal recovery, legacy rainfall migration, module boundaries, API endpoints, and agent tools. The LLM tool loop uses test responses; this does not verify a real provider call.

The existing frontend/app.js ran in a jsdom DOM against the actual local FastAPI HTTP service, displaying two cards, twenty real metric rows, zero missing rows, and two preserved route SVG fallbacks. To repeat this check:

```bash
python -m uvicorn outdoorwise.api.app:app --port 8765
# In another terminal, from the project root; Node 20+ is required.
# jsdom is needed only for this frontend verification.
npm install --prefix /tmp/outdoorwise-ui-check jsdom
NODE_PATH=/tmp/outdoorwise-ui-check/node_modules BASE_URL=http://127.0.0.1:8765 node tests/frontend_smoke.cjs
```

## Verification Limits

Full browser screenshots and online Leaflet map rendering were not visually verified because the browser download returned a damaged archive. Successful DOM and HTTP checks should not be described as a complete visual browser test. The Docker build was not run; Dockerfile includes the newly required config directory. No external LLM credentials were supplied, so a real agent provider was not verified.

Observation timestamps naturally age. The service recalculates fresh, stale, and cache labels at query time rather than reusing old snapshot labels. Current observations are not future 30- or 60-minute predictions. Live forecasts and comprehensive risk outputs remain unavailable.
