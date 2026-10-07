# OutdoorWise — Environmental Data Pipeline Demo

OutdoorWise combines two curated Singapore running routes with environmental observations, route recommendations, and an assistant interface. This version extends the existing demo in place, preserving its frontend, Marina Bay and Woodlands Waterfront routes, GeoJSON files, and rainfall workflow.

The pipeline integrates eight official API endpoints covering ten environmental metrics, stores observations in CSV files, and exposes a shared route environment service. The default data mode is **live**. The default assistant mode is a fixed rule-based demonstration. The existing recommendation baseline uses route distance and rainfall; a comprehensive environmental risk model is not connected yet.

## Requirements

- Python 3.11 or later.
- Linux or macOS. On Windows, use WSL or Docker because the CSV repository uses `fcntl` for cross-process locking.
- Internet access to collect live observations. Previously collected data can be read without fetching again.

## Quick Start

Run these commands from the extracted project directory:

```bash
cd outdoorwise-demo
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export OUTDOORWISE_DATA_MODE=live
python -m outdoorwise.cli collect
python -m outdoorwise.cli run --horizon 30
python -m uvicorn outdoorwise.api.app:app --host 127.0.0.1 --port 8000
```

Open [the application](http://127.0.0.1:8000). Each route card displays metric values, sources, station distances, observation and fetch times, freshness states, and delivery labels. Hover over a metric row to inspect its matching method, source update time, and status explanation. API documentation is available at [the backend documentation page](http://127.0.0.1:8000/docs).

The **Refresh observations** button collects all configured sources. A failed source produces a `partial` result while collection continues for the other sources. Existing observations remain available with explicit status labels.

The package includes CSV files from a verified live collection. Their timestamps naturally become stale. Run `collect` again to refresh them. Starting the server in live mode reads stored live observations; it does not automatically fetch data or substitute demo values.

## Collection and Demo Commands

```bash
# Collect only sources whose configured polling interval has elapsed.
python -m outdoorwise.cli collect --due

# Run the test suite.
python -m pytest -q

# Collect explicitly synthetic observations.
OUTDOORWISE_DATA_MODE=demo python -m outdoorwise.cli collect

# Start the application with demo observations and simulated forecasts.
OUTDOORWISE_DATA_MODE=demo python -m uvicorn outdoorwise.api.app:app
```

Start continuous collection in a separate terminal:

```bash
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli watch
# Inspect record counts and the last worker report.
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli status
```

`watch` checks configured source intervals every 30 seconds, persists live history, and resumes scheduling from ingestion logs after restart. Stop it with Ctrl+C. Only one continuous worker can own a data directory. `collect --due` remains a one-shot entry point; `collect` without `--due` forces all sources.

The collector process and host must remain running. The frontend runs independently. See [continuous collection](docs/LIVE_COLLECTION.md) for shutdown, Docker Compose, recovery, and monitoring instructions.

Live and demo observations are isolated using `source_kind`. The latest route CSV views represent the mode used by the most recent refresh. The shared service recalculates results for the selected mode and query time.

## Project Structure

| Responsibility | File or directory |
|---|---|
| API URLs, polling intervals, timeouts, retries, and freshness thresholds | `config/environment.toml` |
| Independent collectors for each API endpoint | `outdoorwise/collectors/` |
| Field, unit, aggregation window, and type validation | `outdoorwise/contracts/environment.py` |
| Module protocols | `outdoorwise/contracts/ports.py` |
| Single writer, deduplication, revisions, and atomic persistence | `outdoorwise/storage/repository.py` |
| Independent metric matching and shared environment access | `outdoorwise/services/route_environment.py` |
| Continuous collector and scheduler | `outdoorwise/pipeline/worker.py` |
| Collection and module orchestration | `outdoorwise/pipeline/runner.py` |
| Module composition and implementation selection | `outdoorwise/bootstrap.py` |
| Existing frontend with route environment tables | `frontend/` |
| Route catalog and GeoJSON geometry | `data/catalog/` |
| Observations, source mappings, route summaries, and ingestion logs | `data/runtime/*.csv` |
| Integration templates for team members | `templates/module_template.py` |

## Environmental Metrics

| Metric | Canonical unit | Aggregation window |
|---|---|---|
| Rainfall | `mm` | 5-minute accumulation |
| Wind speed | `m/s` | 10-minute mean |
| Wind direction | `degree` | 10-minute mean |
| Air temperature | `degC` | 1 minute |
| Relative humidity | `%` | 1 minute |
| PM2.5 | `ug/m3` | 1 hour |
| PSI | `index` | 24 hours |
| PM10 | `ug/m3` | 24 hours |
| Official WBGT | `degC` | 15-minute mean |
| Official heat stress level | `category` | Corresponding 15-minute WBGT observation |

PM10 is extracted from the PSI API's concentration field, not its PM10 sub-index. WBGT and heat stress come directly from the official endpoint. Polling intervals and publication cadence are separate from aggregation windows.

Each metric selects its own available source. Station-based metrics use the route's first GeoJSON coordinate as a representative point. Regional air quality metrics use the configured source region: `south` for Marina Bay and `north` for Woodlands Waterfront. This version does not implement along-route sampling or regional polygon containment.

## CSV Storage and Data Status

The existing `routes.csv` and GeoJSON files remain in `data/catalog/`. Runtime storage includes:

- `locations.csv`: source station and region metadata.
- `weather_observations.csv` and `weather_observation_versions.csv`: rainfall, wind speed/direction, temperature, and humidity.
- `air_quality_observations.csv` and `air_quality_observation_versions.csv`: PM2.5, PSI, and PM10.
- `heat_stress_observations.csv` and `heat_stress_observation_versions.csv`: official WBGT and heat stress.
- `route_source_mapping.csv`: route-to-source mappings for each metric.
- `route_environment_latest.csv`: the latest route environment summary.
- `ingestion_runs.csv`: collection outcomes and received, inserted, revised, and unchanged record counts.

Observation records distinguish `observed_at`, `source_updated_at`, and `fetched_at`. Every CSV timestamp uses Singapore local time in `YYYY-MM-DDTHH:MM:SS` format, without fractional seconds or a timezone suffix. The repository restores `Asia/Singapore` on read; internal models and HTTP timestamps remain timezone-aware. If a source does not supply an update timestamp, `source_updated_at` remains empty.

Repeated collection does not append duplicate observations. Source corrections update the current observation and retain earlier revisions. CSV writes are serialized through the repository and use temporary files with atomic replacement. A pending transaction journal supports recovery of interrupted multi-file updates.

Freshness is represented by `fresh`, `stale`, or `missing`. Delivery is represented by `live`, `cache`, `demo`, or `unavailable`. Missing measurements remain `None` or `null`; they are never replaced with zero.

## Shared Module Interface

Team modules read structured data through a common interface:

```python
from datetime import datetime, timezone
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import Settings

pipeline = build_pipeline(Settings.from_env())
environment = pipeline.get_route_environment(
    'marina_bay',
    datetime.now(timezone.utc),
)
```

The equivalent HTTP endpoint is:

```text
GET /api/routes/marina_bay/environment?as_of=2026-10-05T03:40:00Z
```

`as_of` must include a timezone. Omit it to query the current environment. The result is a typed `RouteEnvironment` containing metric values, provenance, timestamps, matching details, and status labels.

Consumer modules must not read or write CSV files directly or independently call environmental APIs. Implementations are selected in `bootstrap.py`. A future PostgreSQL adapter should preserve the repository protocol and observation revision semantics.

## Predictions, Risk Assessment, and Agentic AI

Current observations are separate from future 30- or 60-minute forecasts. The live prediction and comprehensive risk modules currently return `unavailable`. Demo forecasts use `is_mock=true`. Prediction outputs are stored separately in `data/runtime/predictions_latest.json`, never in the environmental observation table.

The existing assistant supports a chat-completions tool loop. Configure a real provider with:

```bash
export OUTDOORWISE_AGENT_MODE=llm
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=your-provider-model
export LLM_API_KEY=your-key
```

No provider credentials were supplied during verification, so real LLM calls have not been verified. The default demo assistant follows a fixed tool sequence. Its tools consume structured environmental data and module outputs. The `get_route_environment` tool accepts `route_id` and an optional `as_of` timestamp.

## Verification

The verified live collection successfully fetched all eight API endpoints and inserted **234 real observations**. Both routes generated ten environmental metric summaries each. The test suite passed **20 tests**, covering parsing, deduplication, revisions, historical queries, failure isolation, caching, retries, current-table initialization, and module interfaces.

The existing frontend passed a DOM integration check against the actual HTTP backend, displaying two route cards and twenty environmental metric rows. Full browser screenshots and the online Leaflet map were not visually verified because the browser download failed. Real LLM provider calls and Docker builds were not verified.

## Documentation

- [Continuous live collection](docs/LIVE_COLLECTION.md)
- [API configuration and source semantics](docs/API_CONFIG.md)
- [CSV schema and persistence rules](docs/CSV_SCHEMA.md)
- [Architecture and module boundaries](docs/ARCHITECTURE.md)
- [Six-person ownership and module handoff](docs/TEAM_HANDOFF.md)
- [Verification results and limitations](docs/VERIFICATION.md)

## Updating an Existing Installation

Stop the collection worker and web server before replacing code. Preserve the data/runtime directory when replacing an existing installation using the current category tables. Install the updated code and run `python -m outdoorwise.cli status` to inspect the database, then restart the collection worker and frontend.

Repository initialization creates missing current tables and replays interrupted writes. All CSV time fields use local Singapore time at second precision. See docs/CSV_SCHEMA.md for the storage contract.
