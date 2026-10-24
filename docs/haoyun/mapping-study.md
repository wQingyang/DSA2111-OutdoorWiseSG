# Route station-matching comparison

## Purpose

This independent offline experiment compares station matching for every predefined route in `data/catalog`:

1. `nearest_start`: the nearest usable station to the first GeoJSON coordinate.
2. `nearest_end`: the nearest usable station to the last GeoJSON coordinate.
3. `along_route_500m`: the nearest usable station to samples spaced at approximately 500 m along the complete geometry, including both endpoints.

The experiment reuses the production route catalog loader, metric/source contracts, configured station distance limit, freshness thresholds, and geodesic distance function. It reads one repository snapshot for a single timezone-aware `as_of` time and uses that same snapshot for all methods. A fresh usable observation is preferred over stale usable observations, as in `RouteEnvironmentService`; if no fresh observation is available, a stale usable observation can still match and is labelled stale. Missing numeric and category values remain missing. Stations beyond the configured maximum distance (15 km for this run) are not matched.

This script does not collect data or write to the observation tables. It does not change the production recommendation flow or route risk scores.

## Regional metrics

PM2.5, PSI and PM10 use curated route-to-region assignments in the existing configuration. They are reported under `metric_class=region` and `method=regional_configured_assignment`, with `matched_location_type=region`. Region centres are not treated as stations, no station distance is calculated for them, and they are not included in the three station-method comparison groups. Their single configured assignment per route is included in the CSVs so the environmental values and freshness remain visible and distinct.

## Reproduction

Run from the repository root with the project virtual environment:

```bash
.venv/bin/python scripts/compare_route_mapping.py --data-mode demo --as-of 2026-10-24T22:40:30+08:00
```

The assessment time is **2026-10-24 22:40:30 Asia/Singapore** (`2026-10-24T14:40:30+00:00`). The source commit is **`79dc7f01d586341d9b451c75d123e1f89a61befa`** (`haoyun/mapping-demo-validation`). The input data mode is **demo (synthetic observations)**. The script reads `data/runtime` and writes only these outputs:

- `docs/haoyun/mapping-results/demo/per_sample.csv`
- `docs/haoyun/mapping-results/demo/summary.csv`

`per_sample.csv` has one row per tested sample and metric (plus the separate regional assignment rows), including coordinates, matched location ID and coordinates, distance, observed numeric/category value, observation time and freshness. `summary.csv` has sample and match counts, total and fresh coverage ratios, fresh/stale counts, distinct matched location count, mean/maximum distance, and mean/maximum numeric observation value. An empty numeric summary means no numeric values were matched (for example, a category metric or entirely missing values), not zero.

For `along_route_500m`, mean and maximum numeric values are summaries of the numeric values at matched route samples. They are **not ground-truth measurements along the route**, and nearest-station matching does not establish that the station represents the conditions at a sample point.

## Results

The run produced **1,317 per-sample rows** and **288 summary rows** across all **12 predefined routes**. There are 1,281 station sample rows and 36 separately labelled regional assignments.

| Station method | Route/metric comparisons | Mean match coverage | Mean fresh coverage | Mean distinct stations per route/metric | Mean distance per matched sample |
|---|---:|---:|---:|---:|---:|
| Nearest start | 84 | 100% | 28.6% | 1.00 | 3.857 km |
| Nearest end | 84 | 100% | 28.6% | 1.00 | 3.857 km |
| Along route, approximately 500 m | 84 | 100% | 28.6% | 1.17 | 3.802 km |

The distance averages above average the per-route/per-metric summary distances; they are descriptive for this synthetic snapshot. The along-route method produced 1,113 station sample rows. Its mean coverage is 100% because every sample in this run had a usable station within 15 km. Of all station sample rows, **366 were fresh and 915 were stale** at the assessment time. All **36 regional assignments were fresh**. Fresh and stale availability is also recorded separately for each route/method/metric in `summary.csv`.

## Limitations

- Demo observations are synthetic and cannot establish real station coverage, environmental accuracy, or route suitability.
- Freshness labels reflect the configured age thresholds at the fixed assessment time. Stale observations were retained as stale rather than refreshed or relabelled.
- The 12 catalog routes are the current predefined set. The longest along-route comparison generated 20 samples; the experiment sampler has no 30-point cap, and a separate test verifies a route with more than 30 samples and both endpoints.
- A station may be selected for several nearby sample points. The reported along-route mean/maximum are summaries of those matched sample values, not spatial interpolation or independent measurements at the route.
- This is a mapping comparison only. It does not modify or validate risk scoring, recommendation ranks, route geometry, or the curated regional assignments.

## Follow-up analysis

The saved CSV totals were checked against their grouped per-sample records. Along-route sampling matched multiple stations for all seven station metrics on Singapore Botanic Gardens and West Coast Park. For this synthetic snapshot, start and end matched numeric values agreed; along-route matched-sample means differed only for rainfall on those two routes. The analysis excludes arithmetic comparisons of wind direction and keeps regional PM2.5, PSI and PM10 separate from station results. These differences do not establish measurement accuracy.

See [the detailed analysis](mapping-results/demo/analysis.md) and its reproducible figures: [rainfall matching map](figures/demo-rainfall-matching-map.png), [station-distance comparison](figures/demo-rainfall-station-distance.png), and [along-route fresh coverage](figures/demo-fresh-coverage.png). Regenerate them from the saved CSVs with:

```bash
MPLCONFIGDIR=/tmp/outdoorwise-mpl-config MPLBACKEND=Agg .venv/bin/python scripts/analyze_route_mapping.py
```

## Live-retry results

The saved live-retry records contain 1,317 sample rows and 288 summaries across 12 routes. The assessment time recorded in every sample row is **24 Oct 2026, 23:09:41 SGT** (UTC: `2026-10-24T15:09:41.280461+00:00`). All 1,281 station sample assignments and 36 regional assignments are fresh in this snapshot; all three station methods have 100% spatial coverage, while start/end cover only their representative points. Along-route matching uses multiple stations for 35 route/metric pairs; Bedok Reservoir has three distinct rainfall stations. All matched rainfall values are zero, so rainfall-value differences cannot be demonstrated. These records show method feasibility for this snapshot, not measurement accuracy or route safety; repeated assignments to a station are not independent observations. Regional PM2.5, PSI and PM10 remain separate, and wind direction is excluded from arithmetic comparison.

See [live-retry analysis](mapping-results/live-retry/analysis.md) and the [rainfall matching map](figures/live-rainfall-matching-map.png), [station-distance comparison](figures/live-rainfall-station-distance.png), and [fresh coverage figure](figures/live-fresh-coverage.png). Reproduce the analysis from the saved CSVs with:

```bash
MPLCONFIGDIR=/tmp/outdoorwise-mpl-config MPLBACKEND=Agg .venv/bin/python scripts/analyze_route_mapping.py --input-dir docs/haoyun/mapping-results/live-retry --output-dir docs/haoyun/mapping-results/live-retry --figures-dir docs/haoyun/figures --data-mode-label "Live-retry observations" --figure-prefix live
```

## Final conclusion

The catalog geometries have coincident start and end coordinates for all 12 routes. Their geodesic endpoint separations are therefore 0 m (at the coordinates stored in the catalog). The live-retry experiment has identical start/end station matches for all seven station-based metrics on every route: both methods use the exact same representative point, not merely nearby endpoints.

| Route | Start-to-end distance |
|---|---:|
| Marina Bay waterfront loop | 0 m |
| Woodlands Waterfront out-and-back | 0 m |
| West Coast Park out-and-back | 0 m |
| East Coast Park out-and-back | 0 m |
| Bishan–Ang Mo Kio Park river loop | 0 m |
| Singapore Botanic Gardens garden loop | 0 m |
| MacRitchie Reservoir forest loop | 0 m |
| Pasir Ris Park coastal loop | 0 m |
| Bedok Reservoir Park loop | 0 m |
| Jurong Lake Gardens lakeside loop | 0 m |
| Bukit Timah Rail Corridor out-and-back | 0 m |
| Punggol Waterway out-and-back | 0 m |

Along-route multi-station matching is feasible in the assessed live snapshot: it produced usable station assignments at the route samples, including multiple stations for 35 route/metric pairs. The following **17 numeric route/metric comparisons** have an along-route matched-sample mean that differs from the start-point value. Wind direction is excluded from arithmetic comparison, and categorical heat-stress levels have no numeric mean.

| Route | Metric | Start/end value | Along-route matched-sample mean | Unit |
|---|---|---:|---:|---|
| Bedok Reservoir Park loop | Wind speed | 0.771667 | 0.774239 | m/s |
| Bedok Reservoir Park loop | Air temperature | 27.1 | 27.13 | °C |
| Bedok Reservoir Park loop | Relative humidity | 95.7 | 95.485 | % |
| Bedok Reservoir Park loop | WBGT | 26.4 | 26.05 | °C |
| Bishan–Ang Mo Kio Park river loop | WBGT | 25.6 | 25.6727 | °C |
| East Coast Park out-and-back | Wind speed | 1.02889 | 0.861694 | m/s |
| East Coast Park out-and-back | Air temperature | 28.3 | 27.8125 | °C |
| East Coast Park out-and-back | Relative humidity | 86.6 | 90.5 | % |
| East Coast Park out-and-back | WBGT | 26.5 | 26.3313 | °C |
| Jurong Lake Gardens lakeside loop | WBGT | 25.6 | 25.6429 | °C |
| MacRitchie Reservoir forest loop | Wind speed | 1.33756 | 1.10891 | m/s |
| MacRitchie Reservoir forest loop | Air temperature | 27.2 | 27.5889 | °C |
| MacRitchie Reservoir forest loop | Relative humidity | 92.2 | 90.0333 | % |
| Marina Bay waterfront loop | WBGT | 26.2 | 26.0667 | °C |
| Punggol Waterway out-and-back | Wind speed | 0.771667 | 0.689356 | m/s |
| Punggol Waterway out-and-back | Air temperature | 27.1 | 26.92 | °C |
| Punggol Waterway out-and-back | Relative humidity | 95.7 | 96.48 | % |

All matched rainfall values are zero in this snapshot, so rainfall-value differences cannot be demonstrated. The along-route means summarize values attached to matched sample assignments; a station can be assigned to many samples, so those assignments are not independent observations. Coverage and station distance describe matching availability and separation; neither establishes measurement accuracy. Start/end single-point coverage is not equivalent to whole-route sampled coverage.

Production integration remains a separate task. It requires agreement on along-route aggregation, coverage metadata, and compatibility with the risk module. This comparison alone does not determine those production semantics.
