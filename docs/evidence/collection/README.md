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

## Scope of this evidence

These are dated October 2026 collection records from the earlier two-route
checkout. They do not describe the current route count, test count or deployment
state. `example_run.json` is a historical response, not a current contract fixture.
For current startup, tests, browser checks and limitations use the
[main README](../../../README.md) and [final verification](../../FINAL_INTEGRATION.md).
Archived source counts are not evidence that today's observations are fresh.

## Continuous Worker Verification — 2026-10-07

A finite live worker run completed two checks. All eight official sources succeeded in the first check and inserted 234 new real observations. The CSV now contains 468 live observations, preserving the earlier collection. The second check made no API requests because no source interval had elapsed. Both routes retained ten metric summaries. Worker status was saved as stopped after the finite run.

Worker checks cover restart cooldowns, exclusive worker ownership, persisted status, and real subprocess SIGTERM shutdown. Detailed collection evidence is in continuous_collection_verification.json. This finite run is not an ongoing hosted service; start watch on a host that remains running to accumulate further history. Docker deployment remains unverified.

## Category tables at the recorded collection

The weather, air_quality, and heat_stress observation tables contain 702 real observations across the recorded collections. The most recent recorded live collection succeeded for all eight APIs and added 234 observations. At collection time, each route returned ten real metrics without missing values. All nonempty CSV time fields were verified against YYYY-MM-DDTHH:MM:SS in Asia/Singapore, without fractions or timezone suffixes. See collection_verification.json for counts and source outcomes.

The current test suite covers all three table categories, their revision tables, repeatable initialization, local-time round trips, and repeated fractional timestamp deduplication. The collector is not an ongoing hosted service.
