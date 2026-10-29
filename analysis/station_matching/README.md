# Station-to-route matching experiment

This independent experiment compares the spatial support of environmental
station assignments on the 12 catalog routes. It reads a stored observation
snapshot; it neither collects new measurements nor participates in API startup.

## Methods and interpretation

**Version 1: route start-point matching** assigns each station-based metric to
the nearest usable station at the route start, subject to the configured distance
limit. End-point matching is a control: the saved catalog routes have coincident
start/end coordinates, so their endpoint results agree.

**Version 2: along-route sampling** places samples approximately every 500 m
along cumulative route geometry, including endpoints, then matches a station for
each sample and metric. Unlike production dynamic sampling, the experiment does
not cap samples at 30. The comparison uses the same stored source-kind snapshot,
assessment time, metric units, freshness thresholds and matching limit.

`per_sample.csv` records matched sources, distances, values and freshness.
`summary.csv` groups route/method/metric assignments: sample and matched counts,
mean/maximum distance, distinct stations, spatial coverage, fresh coverage, and
matched numeric means/maxima. Regional PM2.5/PSI/PM10 assignments are kept separate.
Wind direction is excluded from arithmetic value comparisons because angles wrap.

A smaller station distance is a spatial proxy, not proof of measurement accuracy.
Repeated assignments to one station are not independent observations. Single-point
coverage and whole-route sampled coverage answer different questions; implementation
complexity and spatial representativeness are separate design considerations.

## Evidence and relation to production

The preserved [study](results/study.md), [synthetic analysis](results/demo/analysis.md)
and [live-retry analysis](results/live-retry/analysis.md) explain the findings.
The live-retry snapshot has 1,317 rows, 288 summaries and 12 routes; 35 route/metric
pairs match multiple stations. Seventeen numeric comparisons differ from the
start-point result. All matched rainfall values are zero, so that snapshot cannot
demonstrate rainfall-value differences. These findings establish matching
feasibility for the saved snapshot, not route safety or measured weather accuracy.

Production catalog matching remains start-point/configured-region matching.
Dynamic routes use bounded along-route sampling, conservative component maxima
and explicit incomplete-coverage handling. The independent experiment does not
change either production method or determine the risk aggregation policy.

## Reproduce without overwriting evidence

Run from the repository root after installing `.[dev]`. Analyse the saved CSVs
into a new temporary directory (no provider access, training or collection):

```bash
MPLCONFIGDIR=/tmp/outdoorwise-mpl MPLBACKEND=Agg .venv/bin/python \
  analysis/station_matching/scripts/analyze_route_mapping.py \
  --input-dir analysis/station_matching/results/live-retry \
  --output-dir /tmp/outdoorwise-matching-analysis \
  --figures-dir /tmp/outdoorwise-matching-analysis/figures \
  --data-mode-label "Live-retry observations" --figure-prefix live
```

To create a comparison, use a **separate copied data root** containing `catalog/`
and `runtime/` with the desired observations. The repository adapter can initialize
missing metadata, so do not point this command at protected operational data:

```bash
.venv/bin/python analysis/station_matching/scripts/compare_route_mapping.py \
  --data-root /tmp/outdoorwise-matching-data --data-mode live \
  --as-of 2026-10-24T23:09:41.280461+08:00 \
  --output-dir /tmp/outdoorwise-matching-comparison
.venv/bin/python -m pytest -q tests/test_route_mapping_experiment.py
```

Historical raw observations needed to reproduce a saved match may no longer be
present in a different runtime snapshot; the saved CSVs remain the authoritative
inputs for reproducing the published analysis. `results/live/` preserves an earlier
collection attempt, and `results/live-retry/` the subsequent successful snapshot.
`figures/` retains the original research figures and recorded demo screenshots.
`archive/` contains dated provenance/demo records with superseded UI instructions;
use the main README for current application operation.
