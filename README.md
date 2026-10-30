# OutdoorWiseSG

OutdoorWise recommends Singapore running routes from geographic data,
environmental observations and running preferences. The catalog has **12 routes**.
Accounts, per-user running history, favourites, difficulty feedback, personalized
ordering, Leaflet maps and GPX export are supported.

- **Tab 1 — Existing route recommendations:** one form and **Find Recommended Routes** action. Live Mode assesses current observations; Historical Mode replays a fixed dataset with explicit prediction limitations.
- **Tab 2 — Generate a dynamic route:** OpenRouter interprets natural-language preferences, the user confirms coordinates, and OpenRouteService (ORS) generates geometry. Manual preferences remain available without the LLM; geometry generation still requires ORS.

Risk and difficulty are provisional engineering estimates. Source freshness,
coverage, unavailable values and geometry-review limitations remain visible.

## Startup options: Local Python, Docker Compose or Local Kubernetes

All three options run the same application: **Tab 1** recommends existing routes using
current environmental observations; **Tab 2** parses natural-language preferences
through OpenRouter and generates routes through OpenRouteService (ORS). Choose
**one** option at a time to avoid duplicate collectors. Use Python 3.11+ for local
startup; macOS/Linux commands below (Windows: WSL or Docker).

### Configure API keys (Local Python and Docker Compose)

Create `.env` in the repository root. Copy `.env.example` with
`cp .env.example .env`; or create `.env` manually. Populate the keys you
need:

```dotenv
# Tab 2: ORS creates route geometry
ORS_API_KEY=your_ors_key
# Tab 2: OpenRouter parses natural-language running preferences
OPENROUTER_API_KEY=your_openrouter_key
# Optional OpenRouter model
OPENROUTER_MODEL=openrouter/free
# Optional public Singapore environmental API key for the collector
DATA_GOV_API_KEY=
```

These are **separate services**: OpenRouter parses preferences, while ORS creates
route geometry. Each can be tested independently; the other key is not needed for
that individual step. `DATA_GOV_API_KEY` is optional for public data collection.
All keys remain server-side.

### Option A — Local Python (two terminals)

**One-time installation** from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

**Terminal 1 — Live environmental collector:**

```bash
cd /path/to/outdoorwise-main
source .venv/bin/activate
# Load optional DATA_GOV_API_KEY (and other settings) if present:
set -a; source .env; set +a
OUTDOORWISE_DATA_MODE=live \
python -m outdoorwise.cli watch --tick-seconds 30
```

Keep this terminal running. `--tick-seconds 30` is a scheduling check interval,
not a promise to fetch each source every 30 seconds. Only **one collector** may
own the same runtime data directory. If you get `A collection worker already
owns this data directory`, first check for and stop the existing collector;
do not blindly remove its lock.

**Terminal 2 — FastAPI backend and both frontend tabs:**

```bash
cd /path/to/outdoorwise-main
source .venv/bin/activate
set -a; source .env; set +a
OUTDOORWISE_APP_MODE=live OUTDOORWISE_DATA_MODE=live \
python -m uvicorn outdoorwise.api.app:app \
  --host 127.0.0.1 --port 8001 --workers 1
```

Open **http://127.0.0.1:8001** (API docs: `/docs`). Local Python does **not**
automatically load `.env`, so run the `set -a; source .env; set +a` command in
each terminal before starting a process. The API reads existing observations;
it does not fetch them on startup.

To test **Tab 1 Historical Mode**, stop Terminal 2 with Ctrl+C and restart it
with `OUTDOORWISE_APP_MODE=historical` (other arguments unchanged). Historical
mode does not change Tab 2. You can inspect the collector without starting a
second collector using `OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli status`.

For collection independent of Terminal, optional [macOS launchd setup](docs/LOCAL_COLLECTOR_MACOS.md)
supervises the same worker and preserves host CSV history. It is not installed
automatically and cannot collect while the Mac is asleep or powered off.

### Option B — Docker Compose (two services, one command)

Install and **start Docker Desktop** (or another Docker Engine). Check
`docker info` and `docker compose version`; if the daemon is unavailable,
start Docker Desktop before trying to build. Keep `.env` in the repository root.
Compose reads this file for variable substitution; there is no need to `source`
it for Docker Compose.

Stop any locally running collector and FastAPI process, then execute:

```bash
cd /path/to/outdoorwise-main
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Docker Compose runs exactly two services: `collector` (continuous data
collection) and `app` (FastAPI plus Tab 1 and Tab 2). Open
**http://localhost:8000** (API docs: `/docs`). To inspect operation:

```bash
docker compose logs --tail=100 collector
docker compose logs --tail=100 app
curl -f http://localhost:8000/api/health
curl -f http://localhost:8000/api/ready
```

Both containers share the **`outdoorwise-runtime` named volume** at
`/app/data/runtime`. This is distinct from your host's `data/runtime` folder;
existing locally collected CSV/SQLite/JSON data is **not automatically copied**
into the volume. Container restarts retain the volume, whereas
`docker compose down -v` **deletes** it. Use `docker compose down` to stop the
services without removing the named volume.

To choose Tab 1 Historical Mode in Compose, set
`OUTDOORWISE_APP_MODE=historical` in `.env` and recreate the app using
`docker compose up -d --force-recreate app`; return it to `live` for the normal
live workflow. The collector continues collecting live data independently.

### Option C — Local Kubernetes (Docker Desktop kind)

The accepted setup uses Docker Desktop kind, one Linux ARM64 node, one app and
one collector, with a shared 2 GiB PVC. Follow the [local Kubernetes setup guide](deploy/README.md#local-kubernetes-fresh-machine-setup)
to enable the containerd image store, verify context/storage, stop Compose, build
the image and create `outdoorwise-secrets` using hidden prompts. Kubernetes does
not load `.env`. After those prerequisites:

```bash
kubectl --context docker-desktop apply -k deploy/k8s
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=300s
kubectl --context docker-desktop -n outdoorwise port-forward --address 127.0.0.1 service/outdoorwise 8000:80
```

Open **http://127.0.0.1:8000** while port-forward runs. The guide covers image
availability, validation, port conflicts, safe restarts and storage preservation.
Do not delete the PVC or namespace to stop the application.

### Runtime and data modes

`OUTDOORWISE_APP_MODE` selects Tab 1 (`live` by default, or `historical`);
changing it requires an API restart/recreation. It is independent of
`OUTDOORWISE_DATA_MODE` (`live` or synthetic `demo`). The frontend reads mode
metadata from `/api/health`; there is no mode switch in the UI.
`OUTDOORWISE_DATA_ROOT` defaults to `./data`, with immutable `catalog/` and
writable `runtime/` data. Live Mode supports **Now only**. Missing or stale
observations stay unavailable rather than being replaced by historical or
synthetic values.

```
IMPORTANT NOTE — Live Mode startup and data freshness

On the first run (or after a period without collection), the collector may need time to retrieve the required live environmental observations. Keep the collector running and allow the data to populate before evaluating routes.

The risk score is shown only when sufficient required inputs are available and pass the application's freshness checks. Since sources update at different intervals, there is no fixed waiting time (but no longer than 30 min). If the risk score remains unavailable, check the collector logs and the displayed freshness indicators rather than repeatedly restarting the app.
```

## Historical behavior

Historical Tab 1 always uses the frozen **15 Oct 2026, 19:15 SGT** reference and
`snapshot_20261015`, independently of operational observations. Departures are
**Now, +30, +60 minutes**; duration is a separate activity preference.

Now uses historical observations for numerical departure risk and shared weighted
ranking. Delayed departures retain native WBGT persistence point evidence, but
unsupported rainfall/wind targets and off-grid PM2.5 keep overall risk unknown.
Those routes use explicitly labeled fallback ordering. Full-run exposure risk is
separate and remains unknown where continuous forecast coverage is unsupported.
Prediction Details distinguishes methods, inputs, native targets, available
exact-target ground truth and saved offline metrics. No request trains a model.

Historical completed-run recording is disabled; favourites and GPX remain available.
**Tab 2 always uses its current-environment workflow in both application modes.**
See [architecture](docs/ARCHITECTURE.md), [prediction inventory](docs/PREDICTION_MODELS.md)
and [current verification/limitations](docs/FINAL_INTEGRATION.md).

## Repository guide

| Area | Responsibility |
|---|---|
| `outdoorwise/api/`, `bootstrap.py`, `cli.py` | HTTP workflow, composition and explicit collection commands |
| `collectors/`, `pipeline/`, `storage/`, `contracts/` | Validated ingestion, scheduling, CSV v3 persistence and typed contracts |
| `services/`, `modules/`, `routing/` | Catalog matching, risk/eligibility/ranking and ORS dynamic geometry |
| `accounts/`, `personalization/`, `difficulty/`, `export/` | Identity, user adaptation, effort estimates and GPX |
| `llm/`, `frontend/` | OpenRouter interpretation and shared browser interface |
| `prediction/`, `scripts/evaluate_frozen_forecasts.py` | Protected research training/inference/artifacts and offline evaluation |
| `analysis/station_matching/` | Independent spatial matching methods, scripts, results and figures |
| `tests/`, `docs/`, `deploy/` | Regression checks, technical references and deployment preparation |

Package areas in the table are under `outdoorwise/` unless shown at repository root.
Environmental observations use CSV; account/session records use SQLite; personalization
uses atomic per-user JSON. These stores are intentionally distinct.

## Report analyses

[`analysis/`](analysis/README.md) contains supporting experiments and evaluations
for the DSA2111 final report and presentation, including data freshness and
V1 versus V2 station matching. See the index for reproduction instructions and
guidance on adding independent analyses.

## Validation and deployment

Frontend checks require the Node versions declared in `package.json` and installed
Chrome/Chromium (`CHROME_PATH` can select it):

```bash
npm ci
.venv/bin/python -m pytest -q
npm test
npm run test:browser
docker compose config --quiet
kubectl kustomize deploy/k8s
git diff --check
```

Tests use temporary storage and recorded/synthetic/provider fixtures. Browser tests
also start isolated real FastAPI servers in both application modes. They do not
establish real provider access or deployment success. Current results are recorded
in [FINAL_INTEGRATION.md](docs/FINAL_INTEGRATION.md).

Docker and Kubernetes configurations are prepared, with one API worker/replica and
one collector sharing persistent runtime storage. Local Docker Desktop Kubernetes
acceptance passed; see the [acceptance report](deploy/LOCAL_KUBERNETES_ACCEPTANCE.md)
and [deployment instructions](deploy/README.md). Cloud acceptance remains future work.
Never ship local credentials or operational user files as image contents.

Technical references: [CSV v3](docs/CSV_SCHEMA.md), [source semantics](docs/API_CONFIG.md),
[collection](docs/LIVE_COLLECTION.md), [risk policy](docs/ENVIRONMENTAL_RISK.md),
[personalization](docs/PERSONALIZATION.md), [location/access](docs/STARTING_LOCATION.md),
[station-matching experiment](analysis/station_matching/README.md),
[cleanup audit](docs/REPOSITORY_CLEANUP.md).
