# Mapping experiment analysis

## Verification and scope

The saved CSVs agree with the reported experiment totals: **1,317 per-sample rows**, **288 summary rows**, and **12 routes**. They contain **1,281 station sample rows** and **36 regional assignment rows**. The three station methods each have 84 route/metric summaries. Along-route samples total 1,113; start and end methods each represent one point for each route and station metric. Grouped match, freshness, distance, and numeric-value fields in the summary CSV were rechecked against `per_sample.csv`.

The assessment time is **2026-10-24T22:40:30+08:00**. All observations are synthetic demo data. Regional PM2.5, PSI and PM10 assignments are excluded from the station analyses below.

## Reproduction

From the repository root, regenerate this analysis and its figures using the saved CSVs:

```bash
MPLCONFIGDIR=/tmp/outdoorwise-mpl-config MPLBACKEND=Agg .venv/bin/python analysis/station_matching/scripts/analyze_route_mapping.py
```

## Routes and metrics matching multiple stations

Along-route matching found more than one distinct station on these routes and metrics:

| Route | Station-based metrics with multiple stations | Rainfall station IDs |
|---|---|---|
| Singapore Botanic Gardens garden loop | rainfall, wind speed, wind direction, air temperature, relative humidity, wbgt, heat stress level | DEMO_CENTRAL, DEMO_SOUTH (rainfall example) |
| West Coast Park out-and-back | rainfall, wind speed, wind direction, air temperature, relative humidity, wbgt, heat stress level | DEMO_SOUTH, DEMO_WEST (rainfall example) |

Every qualifying route/metric had two distinct stations. The rainfall map uses Singapore Botanic Gardens, which qualifies with two rainfall stations. The map displays its full route geometry, start/end, along-route sample points, station markers, and sample-to-station lines.

## Station matching distances

These distances summarize station-to-sample separation. The table averages the 84 route/metric mean distances per method and reports the largest route/metric maximum distance:

| Method | Mean distance (km) | Maximum distance (km) |
|---|---:|---:|
| Nearest start | 3.857 | 8.089 |
| Nearest end | 3.857 | 8.089 |
| Along route (~500 m) | 3.802 | 9.289 |

Start-point and end-point coverage concerns only one representative point each. It is not equivalent to whole-route sample coverage. Along-route matching had 100% spatial match coverage in this snapshot, but that means each sample found a usable station within 15 km; it does not mean every route location was measured. Shorter station distance is not proof of greater measurement accuracy or representativeness.

## Matched numeric values

Wind direction was excluded from arithmetic comparisons because angles wrap around at 360°. Heat-stress level is categorical and has no numeric value. Across 60 complete route/metric numeric comparisons, start and end values agreed in **60** cases. Along-route mean values differed from the start-point value in **2** cases:

| Route | Metric | Start value | End value | Along-route matched-sample mean | Along-route matched-sample maximum |
|---|---|---:|---:|---:|---:|
| Singapore Botanic Gardens garden loop | rainfall | 0 | 0 | 0.184615 | 1.2 |
| West Coast Park out-and-back | rainfall | 1.2 | 1.2 | 1.08 | 1.2 |

The differences are limited to synthetic rainfall values on the two multi-station routes: station fixture values vary there, while the other numeric station metrics have constant fixture values. Along-route means and maxima summarize values attached to matched samples. They are not ground-truth measurements along the route, interpolated estimates, or independent observations at each coordinate.

## Freshness and interpretation limits

Station spatial match coverage was 100% in all three methods. Along-route fresh coverage averaged **28.6%** across the 84 route/metric comparisons; this is a separate measure from spatial match coverage. Of 1,281 station sample rows, **366 were fresh and 915 stale**. Stale usable observations remain included in total matched coverage and are explicitly labelled. All 36 separately identified regional assignments were fresh; they do not contribute to station coverage.

The demo snapshot cannot establish live coverage, real-world freshness patterns, environmental accuracy, or route safety. Freshness depends on the saved timestamps and configured source-specific age thresholds at the assessment time. The experiment also does not establish that a geographically nearest station represents conditions at the route sample. The route catalog is a small predefined set and its geometries retain their existing visual-review status.
