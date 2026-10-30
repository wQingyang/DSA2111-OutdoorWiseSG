# Environmental collection and operational storage

The existing eight collectors normalize official data into the CSV v3 repository.
The API consumes stored snapshots; it does not start a worker or collect on each
recommendation. Ordinary Live recommendations never invoke historical inference.

## Collection commands

After the [local setup](../README.md#startup-options-local-python-docker-compose-or-local-kubernetes), start one collector against
the same `OUTDOORWISE_DATA_ROOT` as the API:

```bash
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli watch --tick-seconds 30
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli status
# Optional single manual due-source collection:
OUTDOORWISE_DATA_MODE=live python -m outdoorwise.cli collect --due
```

The worker checks immediately, then at the tick interval. TOML source intervals,
not worker ticks or aggregation windows, determine due requests: station sources
poll at 300 seconds; PM2.5, PSI/PM10 and WBGT/heat stress at 900 seconds. Requests
are sequential, with bounded timeout/retry/backoff and spacing. See
[API source semantics](API_CONFIG.md) for units and response contracts.

Keep the process and host running. Host sleep interrupts collection; it does not
backfill missed observations. An explicit Live frontend refresh can also collect.
Historical Tab 1 exposes no refresh control. Application mode does not change the
collector's source-kind setting; live failures never substitute synthetic values.

## Availability, failure and recovery

Observations preserve observation time, first-fetch availability, optional source
update, revision and provenance. A snapshot admits only revisions available by
its query time. CSV timestamps are Singapore local seconds without a timezone
suffix; HTTP timestamps remain aware. See [CSV schema](CSV_SCHEMA.md).

A source failure is logged and other sources continue. Existing observations
remain; the environment service reports stale/missing/cache states. Failed attempts
still respect source cooldowns. Missing is never converted to zero. Storage errors
stop the worker rather than claiming successful collection.

Only one continuous worker may own a runtime directory. Its lifetime lease is
separate from the short CSV writer lock, so API reads/summary updates remain
possible. Do not delete locks while a process runs. SIGINT/SIGTERM waits for the
current bounded request sequence, stops before the next source and records stopped
state. SIGHUP is also handled by new workers. Restart reuses attempt timestamps and revision/deduplication semantics.

`runtime/collection_worker.json` contains the last persisted heartbeat/state,
not proof of a currently running process or fresh upstream data. Inspect its time,
process/container status and `cli status`. The collector probe allows 30 minutes
between completed cycles because all eight sources can exhaust retries. API
readiness tests local catalog/storage access; freshness stays in route responses.

For Terminal-independent collection using the existing Mac runtime directory, see
the optional [macOS LaunchAgent instructions](LOCAL_COLLECTOR_MACOS.md). Configuration
rendering is inert; installation and activation are explicit operator actions.
The same document defines the additive worker/source diagnostics and their limits.

Collection extends the three observation/history categories and refreshes route
mapping views. It never trains a model or writes forecasts into observation
history. CSV rewrites and snapshots grow with history size; monitor disk usage and
cycle duration. Scaling/storage redesign requires a separate decision, not deletion
of collected records.

## Deployment and evidence

Compose mounts the named `outdoorwise-runtime` volume at `/app/data/runtime` in
both services. It does not migrate host runtime users/history automatically. Plain
`docker compose down` retains that volume. Kubernetes keeps one API worker/replica
and one collector sharing durable storage; see [deployment](../deploy/README.md)
for secrets, leases, permissions, probes and future acceptance checks.

[Dated collection evidence](evidence/collection/README.md) preserves earlier real
API request records. Current automated tests use recorded payloads, provider mocks
and temporary storage; they do not establish present external API availability.
