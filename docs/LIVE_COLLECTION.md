# Continuous Live CSV Collection

This extends the existing demo. The existing collectors, routes, observation schema, revision history, repository, and frontend remain in use. The worker adds scheduling; it does not generate simulated data or future forecasts.

## Start Building the History

From the existing project directory, install dependencies and start the collector:

```bash
python -m pip install -e '.[dev]'
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli watch
```

The collector runs immediately and then checks for due sources every 30 seconds. Source intervals come from config/environment.toml: 300 seconds for rainfall, wind speed, wind direction, temperature, and humidity; 900 seconds for PM2.5, PSI/PM10, and WBGT/heat stress. The check interval is not the observation sampling interval. API requests are sequential and their duration adds scheduling delay.

Keep this process and its host running. Closing the terminal or allowing a laptop to sleep stops or suspends collection. This package is not a remotely hosted collection service.

Use a separate terminal for the existing frontend:

```bash
OUTDOORWISE_DATA_MODE=live python -m uvicorn outdoorwise.api.app:app --port 8000
```

The web server and collector share data/runtime. The web server does not need to remain open for the worker to collect. The frontend reads the latest stored observations when route comparisons or refreshes are requested; this change does not add automatic browser polling.

## Inspect the Database

```bash
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli status
```

The status report includes live observation counts, oldest and latest observation timestamps per source, the last collection attempt, route-summary counts, and the worker's last persisted state. collection_worker.json records the PID, start time, heartbeat timestamp, completed cycles, and last collection report.

A worker state of running is a persisted report, not proof that the process is still alive. Inspect updated_at and the process or container status, especially after a forced kill or host failure. Do not edit or delete lock files while a worker is running.

## Stop and Resume

Press Ctrl+C in the collector terminal. SIGTERM is also supported. Shutdown waits for the current bounded API request/retry sequence, stops before starting another source, and persists stopped state. A single retry sequence can take approximately 120 seconds with the current timeouts and backoff settings.

Run the same watch command to resume. The existing CSV rows remain. The worker uses persisted attempt timestamps to determine which sources are due. It does not clear history or reinsert duplicate observations.

Only one continuous worker can own a data/runtime directory. A second worker exits with a clear error. The lifetime worker lease is separate from the short CSV writer lock, allowing the web server to read and update summaries. Manual collect and the frontend refresh button remain available; they can cause additional fetches, but the repository still deduplicates observations.

## Failures and Recovery

A source failure is logged in ingestion_runs.csv. Other sources continue, and retained observations are labelled appropriately by the existing environment service. The worker waits for that source's configured interval after a failed attempt before trying again, rather than retrying on every 30-second check. The collector's existing bounded HTTP retries still apply within each attempt.

Storage errors stop the worker with a nonzero exit code. Its last status is marked failed when possible. The existing repository replays an interrupted CSV transaction journal on restart. Investigate disk failures rather than treating an empty or stale report as successful ingestion.

## Docker Compose

```bash
docker compose up -d --build
# Inspect ongoing collection.
docker compose logs -f collector
# Stop only the collector; the frontend can remain running.
docker compose stop collector
# Resume collection.
docker compose start collector
```

The app and collector services share the existing ./data/runtime bind mount. collector uses restart: unless-stopped and a three-minute graceful shutdown window. Docker builds and deployment have not been verified in this execution environment.

## Finite Verification Run

```bash
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli watch --tick-seconds 1 --max-cycles 2
```

This performs two scheduling checks and exits cleanly. After a successful first collection, the second check should skip sources whose configured intervals have not elapsed. A one-second tick does not request all APIs every second.

## Historical Data and Training

New timestamps extend weather_observations.csv, air_quality_observations.csv, and heat_stress_observations.csv. Upstream corrections update the corresponding current observation; each category has its own observation_versions.csv file retaining earlier revisions. All CSV timestamps use Singapore local time at second precision without an offset suffix. Each worker cycle also refreshes route_source_mapping.csv and route_environment_latest.csv.

This accumulates data from the periods when the worker is running. It does not backfill dates before startup or automatically recover observations missed while the host was offline. Historical backfill should be added separately using verified official historical endpoints and the same ingestion contract.

The two-route demo still ingests available stations and regions across the source responses, retaining useful spatial features for future models. A training dataset and future-rain labels are separate deliverables; the route summaries are not a labelled forecast training set.

The current CSV adapter reads and atomically rewrites history files. Cost and runtime grow with history size. Monitor disk usage and collection duration; partitioned storage or the planned PostgreSQL adapter will be needed as the dataset grows. Do not delete older records merely to make the latest route table smaller.
