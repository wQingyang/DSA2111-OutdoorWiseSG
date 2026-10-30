# Environmental risk, eligibility and catalog recommendation evaluation

This is an offline evaluation of the current rule-based implementation. It tests
controlled behavior and describes archived ranking decisions. It does not measure
clinical safety, forecast accuracy or government API performance. Production
formulas, policies, collectors, application behavior and source datasets are unchanged.

## Reproduce

From the repository root, using the existing environment (Python 3.11+, Pydantic 2,
Matplotlib; exact run versions are saved in `verification.json`):

```bash
.venv/bin/python analysis/risk_model/analyze.py
.venv/bin/python -m pytest -q analysis/risk_model tests/test_environmental_risk.py
```

For comparison without overwriting saved outputs:

```bash
.venv/bin/python analysis/risk_model/analyze.py --output-dir /tmp/outdoorwise-risk-reproduction
```

No network, collectors, model training, application startup or `FileRepository`
construction is used. Socket connection attempts are explicitly forbidden while the
script runs. The pure unbound catalog loader reads the 12 catalog routes; a read-only
adapter supplies archived observations to the production matching service. Source
and data hashes are checked before/after execution and included in verification.
The script fails if a boundary expectation or numerical invariant fails.

## Verified implementation and intended policy

The authoritative policy description is
[`docs/ENVIRONMENTAL_RISK.md`](../../docs/ENVIRONMENTAL_RISK.md); this document
records the evaluation protocol. The actual checked-out implementation was inspected
before selecting the experiments.

| Boundary | Implementation |
|---|---|
| Configured curves, weights, no enabled blocks, freshness | [`config/environment.toml`](../../config/environment.toml) |
| Contracts and validated configurable rules | [`outdoorwise/contracts/risk.py`](../../outdoorwise/contracts/risk.py), lines 16–79 |
| Clamped interpolation | [`outdoorwise/modules/risk.py`](../../outdoorwise/modules/risk.py), lines 9–20 |
| Temporal, contract and spatial availability | Same file, lines 28–86 |
| Component precedence and total | Same file, lines 95–160 |
| Eligibility and inclusive blocks | [`outdoorwise/modules/risk_policy.py`](../../outdoorwise/modules/risk_policy.py), lines 6–25 |
| Catalog station matching | [`outdoorwise/services/route_environment.py`](../../outdoorwise/services/route_environment.py), `_evaluate` |
| Baseline candidate/access filtering | [`outdoorwise/modules/recommender.py`](../../outdoorwise/modules/recommender.py), `rank` |
| Weighted score and ordering | [`outdoorwise/modules/risk_ranking.py`](../../outdoorwise/modules/risk_ranking.py), lines 42–68; [`contracts/risk.py`](../../outdoorwise/contracts/risk.py), lines 105–113 |
| Final removal of blocked routes | [`outdoorwise/pipeline/runner.py`](../../outdoorwise/pipeline/runner.py), lines 85–96 |
| Generic difficulty | [`outdoorwise/difficulty/service.py`](../../outdoorwise/difficulty/service.py), `GenericDifficultyEstimator.predict` |
| CSV/time/version availability | [`outdoorwise/storage/repository.py`](../../outdoorwise/storage/repository.py), lines 29–46, 107–126, 170–188 |

For each numeric input, interpolate linearly between adjacent `(value, score)`
knots and clamp below/above the first/last knot:

| Component/input | Knots |
|---|---|
| Rainfall, mm accumulated in 5 minutes | (0,0), (1,20), (5,60), (10,100) |
| WBGT, °C, 15-minute window | (26,0), (31,50), (33,80), (35,100) |
| PM2.5, µg/m³, one-hour measure | (0,0), (55,25), (150,60), (250,85), (350,100) |
| PSI, rolling 24-hour index | (0,0), (50,15), (100,35), (200,70), (300,90), (400,100) |

Usable numeric WBGT overrides heat categories; otherwise categories Low/Moderate/High
score 20/60/90. Numeric categories change at WBGT 31 and 33 °C without adding a
second heat contribution. Usable PM2.5 overrides PSI. PM10, temperature, humidity
and wind direction do not independently enter this environmental risk aggregate.
Wind contributes zero by default; its configured 8→0, 20→100 curve is only active
when explicitly enabled. Neutral wind is not evidence of absence of physical hazards.

`R = round(0.35 rain + 0.35 heat + 0.25 air + 0.05 wind, 2)` requires all four
usable components, including wind even if its weight is zero. Missing data is not
renormalized, and unavailable values never become observed zeros. A source/unit/window
mismatch, missing observation/fetch timestamp or future observation/fetch/provider-update
timestamp prevents use. Freshness is inclusive at 900 seconds for rainfall/wind,
2700 seconds for WBGT and 7200 seconds for PM2.5/PSI, based on observation age at
evaluation. Cached delivery does not alone make a measurement stale.

Station coverage bands are ≤1, ≤3, ≤5 and >5 km; beyond 5 km, configured approximate
estimates are allowed through 15 km with very-low confidence. Low/very-low coverage
causes caution. Regional pollution uses curated coarse regions, not station-distance
confidence. Along-route matching is not part of this catalog evaluation.

Eligibility is unknown for incomplete risk unless a supported enabled block triggers.
Complete assessments receive caution for total ≥40, any selected component ≥70,
categorical heat or PSI fallback, low/very-low spatial quality, or simulated data;
otherwise eligible. Numerical risk labels are low <40, elevated [40,70), high ≥70.
Eligibility is not a safety guarantee. **No hard blocks are configured.** For boundary
testing only, five separate in-memory synthetic policies use rainfall 5, WBGT 33,
PM2.5 150, PSI 100 and wind 20 as inclusive blocking thresholds. These are chosen test
values, not deployed or independently endorsed safety limits. Blocks examine usable
raw inputs even if that input is not selected in the aggregate (e.g. PSI alongside
usable PM2.5, or neutral wind). They can override incomplete assessments. Approximate
station evidence requires explicit rule authorization; stale evidence cannot block.

For target distance `T`, route distance `d`, access distance `a`, predicted difficulty
`g` and target difficulty `t`:

```text
D = 100 max(0, 1 - |d-T|/T)
A = max(0, 100-2a), or 50 with no user location
F = 100 max(0, 1 - |g-t|/4)
S = round(.45(100-R) + .25D + .15A + .15F, 2)
```

Complete eligible/caution candidates share descending `S` order. Unknowns follow
with a null weighted score and legacy fallback; explicit blocks are removed. Score
ties use original baseline rank then route ID. The original baseline uses
`100 - 10|d-T| - 2a - 50p` when access/forecast are available, omitting unavailable
terms, and ties by route ID. Here no forecast or user location is provided, so
that baseline is distance-only. Personalization is outside this evaluation.

## Experimental methods

**1. Sensitivity.** Fix Marina Bay and fresh controlled inputs: rainfall 0, WBGT 26,
PM2.5/PSI 0, wind 2 m/s, category Low, station distance 0.5 km, evaluation/fetch/observation
time October 15, 2026 12:00 SGT. `source_kind=live` exercises the ordinary policy
branch only; these fixtures are explicitly synthetic experimental assignments, not
live observations. Independently vary rainfall 0–15, WBGT 20–40, PM2.5 0–450 and
PSI 0–500, adding exact curve knots, the component-caution crossings and ±0.001
neighbors. PSI is evaluated twice: missing PM2.5 activates fallback; usable PM2.5
keeps PSI out of the score. Check nondecreasing selected component scores only
within these fixed branches. A branch change or saturation need not strictly
increase total score. Component risks, total, selected input and eligibility are
exported for every sample. Figure 1 plots actual deterministic rule evaluations;
lines describe a controlled transfer function, not interpolated historical weather.

**2. Boundaries.** Explicit expected eligibility/risk labels derived from the
documented policy cover observed zeros, saturation, missing/future/stale data,
inclusive freshness boundaries, categorical/PSI fallbacks, spatial limits, component
caution and total-risk thresholds, inclusive synthetic blocks and approximate-evidence
authorization. Expected statuses are written independently of actual outputs. A pass
means rule conformance for that case, not classification accuracy. Conditional
`expected_risk=any` and `expected_level=any` mean those fields are not asserted.

**3. Ranking.** Use all 12 catalog geometries and fixed target 5 km, difficulty 3,
no location/access filter, no forecast, no personal profile. Use production generic
difficulty identically in all methods. Compare:

1. Distance-only order: absolute target-distance difference, then route ID, retaining
   the same known-before-unknown grouping and block exclusion.
2. No explicit environmental recommendation term: environment weight 0; remaining
   .25/.15/.15 weights rescale by 1/.55 to sum to one. This is an ablation baseline,
   not a production configuration change. Generic difficulty still contains environmental
   inputs, so this is **not** a wholly environment-free ranking.
3. Unmodified full risk-aware order.

All methods share assessments, eligibility, candidates and difficulties. Unknowns
remain labelled discovery and never receive an invented risk; complete and unknown
scores are not numerically mixed. Keep blocked routes excluded in every method.
The October 9 and 10 noon snapshots permit assessed comparisons. October 15 noon
tests the all-unknown fallback. These dates are a small descriptive selection, not a
random sample or representative weather survey. A fourth scenario cycles controlled
rain/WBGT/PM2.5 tuples (0,26,0), (1,31,55), (10,35,350) in catalog CSV order. It is
designed to expose sensitivity and cannot estimate real-world benefit.

Export positions, Top-3 IDs/overlap, total absolute rank shift, Top-3 mean reported
risk with its known-risk count, raw rainfall/WBGT/PM2.5/PSI and selected usable heat/air
values. `recorded` indicator means can include stale/unselected values; they are
descriptive records, not a complete assessment. See `matched_environment.csv` for
timestamps and freshness. At the all-unknown snapshot, mean total risk is blank,
not zero. A lower mean internally scored risk after ranking by that score is expected
and does not independently validate safety or user benefit.

**4. Weight sensitivity.** Vary only environmental recommendation weight .30/.45/.60;
rescale other weights proportionally, hold risk curves/weights and eligibility fixed.
Report Top-3 intersection/Jaccard and exact order relative to default. This limited
perturbation is not an optimization or confidence interval.

## Inputs and historical reconstruction

- `data/catalog/routes.csv` and each referenced `data/catalog/*.geojson`.
- `config/environment.toml`.
- `data/runtime/locations.csv`.
- `data/runtime/weather_observation_versions.csv`, `heat_stress_observation_versions.csv`,
  `air_quality_observation_versions.csv`, and their corresponding `*_observations.csv`.
- Actual runtime versions are used, not synthetic demo datasets or prediction outputs.

CSV schema-v3 timestamps without suffix are parsed as **Asia/Singapore**, never UTC.
The adapter reproduces repository version selection: require observation,
version-first-fetch (or fetch) and optional provider-update time ≤as-of; retain the
highest revision per observation key; overlay matching current revisions only if
their retained fetch time is ≤as-of. The matching service then picks the latest
available observation and fresh nearest station, or explicitly stale nearest station
when no fresh station is available. Air regions remain the configured assignments.
No unrecorded historical retrievals are fabricated.

Current location metadata and current catalog/config are applied retrospectively;
historical station metadata versions are not available. This reconstructs assessments
from locally retained evidence, not necessarily every original historical application
decision. Ingestion failure logs are not supplied: these change delivery/reason labels,
not the assessor's temporal/spatial eligibility. The omission is not a claim that
collection was continuously successful. No unavailable payload history is inferred.
Local collection was intermittent; missing periods do not establish provider outages.

## Outputs and report use

- `sensitivity.csv`, `eligibility_boundaries.csv`.
- `ranking_positions.csv`, `ranking_summary.csv`, `weight_sensitivity.csv`.
- `matched_environment.csv`: full input/provenance ledger for each evaluated snapshot.
- `verification.json`: configuration, input/source hashes, case totals and versions.
- `figure_1_risk_sensitivity.{png,pdf}`: controlled 2×2 sensitivity, 7.16-inch width.
- `figure_2_ranking_comparison.{png,pdf}`: positions in all four scenarios, shaded Top-3.
- [`RESULTS.md`](RESULTS.md): compact findings and limitations.
- [`report_sections.tex`](report_sections.tex): suggested IEEE Sections III and IV.
- [`VALIDATION.md`](VALIDATION.md): executed checks, reproducibility and scope.

PNG figures are 300 DPI. PDFs are vector with embedded TrueType fonts and fixed
metadata. Text bounding boxes are checked against the canvas; figures are also
visually inspected. Use the plots across both IEEE columns (`figure*`).

Important edge cases: total risk is rounded before thresholding (a value just below
40 can become caution); missing neutral wind still prevents a total; default total
cannot exceed 95; PSI fallback can mark caution even with a zero air score; confidence
does not impose a separate rank priority. Generic difficulty consumes provided raw
values without independently rechecking freshness, so its use must not be interpreted
as a second freshness guarantee. No production corrections are made by this evaluation.
All findings are limited to documented engineering behavior without external outcome
labels, calibrated exposure estimates, medical validation or validated route-wide conditions.
