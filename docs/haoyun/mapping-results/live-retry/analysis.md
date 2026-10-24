# Mapping experiment analysis

## Verification and scope

The saved CSVs agree: **1,317 per-sample rows**, **288 summary rows**, and **12 routes**. They contain **1,281 station sample rows** and **36 separate regional assignment rows**. Grouped match, freshness, distance, and numeric-value fields in `summary.csv` were recomputed from `per_sample.csv` and verified.

Dataset label: **Live-retry observations** (`source_kind=live`). The assessment time from the sample records is **2026-10-24T15:09:41.280461+00:00**. Regional PM2.5, PSI and PM10 assignments are excluded from station analyses below.

## Reproduction

From the repository root, regenerate this analysis and its figures using the saved CSVs:

```bash
MPLCONFIGDIR=/tmp/outdoorwise-mpl-config MPLBACKEND=Agg .venv/bin/python scripts/analyze_route_mapping.py --input-dir docs/haoyun/mapping-results/live-retry --output-dir docs/haoyun/mapping-results/live-retry --figures-dir docs/haoyun/figures --data-mode-label "Live-retry observations" --figure-prefix live
```

## Routes and metrics matching multiple stations

Along-route matching found more than one distinct station on these routes and station-based metrics:

| Route | Station-based metrics with multiple stations | Maximum distinct stations for a metric | Rainfall sample station IDs |
|---|---|---:|---|
| Bedok Reservoir Park loop | rainfall, wind speed, wind direction, air temperature, relative humidity, wbgt, heat stress level | 3 | S129, S300, S84 |
| Bishan–Ang Mo Kio Park river loop | rainfall, wbgt, heat stress level | 2 | S109, S216 |
| East Coast Park out-and-back | rainfall, wind speed, wind direction, air temperature, relative humidity, wbgt, heat stress level | 3 | S113, S129 |
| Jurong Lake Gardens lakeside loop | rainfall, wbgt, heat stress level | 2 | S180, S229 |
| MacRitchie Reservoir forest loop | wind speed, wind direction, air temperature, relative humidity | 2 | S07 |
| Marina Bay waterfront loop | rainfall, wbgt, heat stress level | 2 | S108, S119 |
| Pasir Ris Park coastal loop | rainfall | 2 | S148, S94 |
| Punggol Waterway out-and-back | wind speed, wind direction, air temperature, relative humidity | 2 | S81 |
| Bukit Timah Rail Corridor out-and-back | rainfall | 3 | S201, S50, S904 |
| Singapore Botanic Gardens garden loop | rainfall | 2 | S120, S90 |
| West Coast Park out-and-back | rainfall | 2 | S203, S230 |

Qualifying route/metric pairs: **35**. The rainfall map selects Bedok Reservoir when its along-route rainfall records contain at least three distinct stations; otherwise it selects a route confirmed by the sample rows to have multiple rainfall stations. It displays route geometry, start/end, sample points, stations, and matching lines on a shared extent.

## Station matching distances

These distances summarize station-to-sample separation. Mean distance averages the route/metric mean distances per method; maximum is the largest route/metric sample distance:

| Method | Mean distance (km) | Maximum distance (km) |
|---|---:|---:|
| Nearest start | 2.415 | 5.193 |
| Nearest end | 2.415 | 5.193 |
| Along route (~500 m) | 2.310 | 5.831 |

Start-point and end-point coverage concerns only each method's single representative point per route and metric. It is not equivalent to whole-route sample coverage. Spatial coverage means a usable station was found within the configured limit; fresh coverage counts only matched samples whose observation passed the freshness threshold.

| Method | Spatial matches | Fresh matches | Missing samples |
|---|---:|---:|---:|
| nearest_start | 84/84 (100.0%) | 84/84 (100.0%) | 0 |
| nearest_end | 84/84 (100.0%) | 84/84 (100.0%) | 0 |
| along_route_500m | 1113/1113 (100.0%) | 1113/1113 (100.0%) | 0 |

Along-route mean spatial coverage across route/metric summaries was **100.0%**, while mean fresh coverage was **100.0%**. Across all station samples, spatial coverage was **100.0%**. Freshness states for along-route samples: fresh 1113, stale 0, missing 0. A smaller station distance does not prove greater measurement accuracy or representativeness.

## Matched numeric values

Wind direction was excluded from arithmetic comparisons because angles wrap around at 360°. Heat-stress level is categorical and has no numeric value. Across 60 complete route/metric numeric comparisons, start and end values agreed in **60** cases. Along-route matched-sample means differed from the start-point values in **17** cases. All matched rainfall values are zero in this snapshot, so rainfall-value differences cannot be demonstrated.

| Route | Metric | Start value | End value | Along-route matched-sample mean | Along-route matched-sample maximum |
|---|---|---:|---:|---:|---:|
| Bedok Reservoir Park loop | wind speed | 0.771667 | 0.771667 | 0.774239 | 0.823111 |
| Bedok Reservoir Park loop | air temperature | 27.1 | 27.1 | 27.13 | 27.7 |
| Bedok Reservoir Park loop | relative humidity | 95.7 | 95.7 | 95.485 | 95.7 |
| Bedok Reservoir Park loop | wbgt | 26.4 | 26.4 | 26.05 | 26.4 |
| Bishan–Ang Mo Kio Park river loop | wbgt | 25.6 | 25.6 | 25.6727 | 25.8 |
| East Coast Park out-and-back | wind speed | 1.02889 | 1.02889 | 0.861694 | 1.02889 |
| East Coast Park out-and-back | air temperature | 28.3 | 28.3 | 27.8125 | 28.3 |
| East Coast Park out-and-back | relative humidity | 86.6 | 86.6 | 90.5 | 91.4 |
| East Coast Park out-and-back | wbgt | 26.5 | 26.5 | 26.3313 | 26.5 |
| Jurong Lake Gardens lakeside loop | wbgt | 25.6 | 25.6 | 25.6429 | 25.9 |
| MacRitchie Reservoir forest loop | wind speed | 1.33756 | 1.33756 | 1.10891 | 1.33756 |
| MacRitchie Reservoir forest loop | air temperature | 27.2 | 27.2 | 27.5889 | 27.9 |
| MacRitchie Reservoir forest loop | relative humidity | 92.2 | 92.2 | 90.0333 | 92.2 |
| Marina Bay waterfront loop | wbgt | 26.2 | 26.2 | 26.0667 | 26.2 |
| Punggol Waterway out-and-back | wind speed | 0.771667 | 0.771667 | 0.689356 | 0.771667 |
| Punggol Waterway out-and-back | air temperature | 27.1 | 27.1 | 26.92 | 27.1 |
| Punggol Waterway out-and-back | relative humidity | 95.7 | 95.7 | 96.48 | 99.6 |

Along-route means and maxima summarize values attached to matched samples. They are not ground-truth measurements along the route or interpolated estimates. A station can be assigned to many nearby samples, so sample assignments are not independent observations. Regional metrics are kept separate and are not part of numeric station comparisons.

## Freshness and interpretation limits

Regional assignment states, kept separately from station results: fresh 36, stale 0, missing 0. Live-retry observations results establish that the methods can produce matches for this saved snapshot. They do not establish measurement accuracy, live coverage beyond the recorded snapshot, or route safety.

Freshness depends on saved timestamps and configured source-specific age thresholds at the assessment time. The experiment does not establish that a geographically nearest station represents conditions at a route sample. Routes/metrics with multiple stations in this snapshot: Bedok Reservoir Park loop (rainfall, wind speed, wind direction, air temperature, relative humidity, wbgt, heat stress level); Bishan–Ang Mo Kio Park river loop (rainfall, wbgt, heat stress level); East Coast Park out-and-back (rainfall, wind speed, wind direction, air temperature, relative humidity, wbgt, heat stress level); Jurong Lake Gardens lakeside loop (rainfall, wbgt, heat stress level); MacRitchie Reservoir forest loop (wind speed, wind direction, air temperature, relative humidity); Marina Bay waterfront loop (rainfall, wbgt, heat stress level); Pasir Ris Park coastal loop (rainfall); Punggol Waterway out-and-back (wind speed, wind direction, air temperature, relative humidity); Bukit Timah Rail Corridor out-and-back (rainfall); Singapore Botanic Gardens garden loop (rainfall); West Coast Park out-and-back (rainfall).
