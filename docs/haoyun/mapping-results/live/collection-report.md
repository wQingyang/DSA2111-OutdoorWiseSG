# Live collection and comparison snapshot

## Collection attempt

Command:

```bash
OUTDOORWISE_DATA_MODE=live .venv/bin/python -m outdoorwise.cli collect
```

The single collection attempt completed with overall status `partial`. Each configured source failed after three attempts with `ConnectError`; no source returned new observations.

| Source | Status | Attempts | Records received | Error |
|---|---|---:|---:|---|
| `nea_rainfall` | failed | 3 | 0 | `ConnectError` |
| `nea_wind_speed` | failed | 3 | 0 | `ConnectError` |
| `nea_wind_direction` | failed | 3 | 0 | `ConnectError` |
| `nea_air_temperature` | failed | 3 | 0 | `ConnectError` |
| `nea_relative_humidity` | failed | 3 | 0 | `ConnectError` |
| `nea_pm25` | failed | 3 | 0 | `ConnectError` |
| `nea_psi` | failed | 3 | 0 | `ConnectError` |
| `nea_wbgt` | failed | 3 | 0 | `ConnectError` |

The last source finished at **2026-10-24T15:03:56.177928Z**. That timezone-aware instant was used as the assessment time for every method in the comparison. Because collection failed, the comparison reflects previously stored live observations available at that time; it does not represent a successful refresh.

Comparison command:

```bash
.venv/bin/python scripts/compare_route_mapping.py --data-mode live --as-of 2026-10-24T15:03:56.177928Z --output-dir docs/haoyun/mapping-results/live
```

## Comparison status

The comparison produced 1,317 per-sample rows and 288 summaries for 12 routes. Across all three station methods, every sample matched a usable stored station, but **0 samples were fresh, 1,281 station samples were stale, and 0 samples were missing**. The 36 regional assignments (PM2.5, PSI and PM10, kept separate from stations) were also all stale. In other words, 100% spatial match coverage must not be read as fresh live coverage: fresh coverage was 0% for all methods and metrics in this snapshot.

Freshness and match status are recorded per row in `per_sample.csv`; summary counts and coverage ratios are in `summary.csv`. The failed requests did not supply new measurements or turn stale values into fresh ones.
