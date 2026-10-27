# Environmental risk and recommendation policy

This release implements observation-based environmental scoring, a separate eligibility policy, and risk-aware ranking after the existing route/access candidate generator. Scores are provisional engineering indicators, **not validated medical risk probabilities, assurances of safety, or navigation approval**. All catalog geometry remains unchanged.

## Composition and compatibility

`bootstrap.py` injects `EnvironmentalRiskAssessor`, `RiskAwareRanking`, and the existing generic difficulty estimator into the pipeline. The assessor reads typed route environments only. `RiskPolicy` applies eligibility independently of numeric scoring. `BaselineRecommender` still generates candidates, applies the access limit, and produces its existing score. The weighted layer preserves each candidate's original baseline rank and only scores/reorders those candidates; explicitly blocked routes are removed from returned recommendations while remaining in `Run.routes` and `Run.risks` for discovery.

The shared weighted layer uses generic difficulty. The authenticated wrapper then reorders surviving candidates by personalized difficulty mismatch, retaining the shared weighted score and rank for tie-breaking. Existing JSON fields and the authenticated outer response (`run`, `target_difficulty`, `recommendations`) are preserved. New request `target_difficulty` defaults to 3 for generic requests; the authenticated request still requires it.

**`score` retains the old baseline value for compatibility; `recommendation_score` is the new normalized weighted score and determines ordering.** Neither is a probability. Full risk components, data quality and warnings are stored once per route under `Run.risks`; recommendations include compact risk/eligibility summaries referencing that route ID. Old clients continue to work. The dashboard displays recommendation_score, final_rank and risk/confidence summaries; the legacy score and original rank are confined to expandable details. See [final verification](FINAL_INTEGRATION.md) for UI checks. Added reasons include distance and observation limitations.

Risk fields are additive to HTTP/Run JSON contracts only. Observation CSV schema v3, units, timestamp format, historical revisions, authentication, and user-history formats are unchanged. No migration or external API call is needed to score stored typed observations. Pipeline run JSON snapshots include the new fields as part of the existing audit persistence.

## Exact scoring formulas

All configuration is under `[risk]` and `[ranking]` in `config/environment.toml`; older configurations without these sections receive the same defaults. Models reject missing/extra weight keys, negative weights, sums other than one, non-finite numbers, unordered curves and out-of-range scores.

For consecutive configured anchors `(x0,y0)` and `(x1,y1)`, normalization is:

```text
s(x) = y0 + (x - x0) * (y1 - y0) / (x1 - x0)
```

Clamp to the first/last score outside the anchor range. Missing/non-finite values remain null, never zero.

| Component | Default input and curve anchors `(input, score)` |
| --- | --- |
| Rainfall | 5-minute accumulation, mm: `(0,0), (1,20), (5,60), (10,100)` |
| Heat | WBGT, degC: `(26,0), (31,50), (33,80), (35,100)` |
| Air quality primary | 1-hour PM2.5, ug/m3: `(0,0), (55,25), (150,60), (250,85), (350,100)` |
| Air quality fallback | 24-hour PSI index: `(0,0), (50,15), (100,35), (200,70), (300,90), (400,100)` |
| Wind | Neutral `0` with a usable wind-speed observation by default. Optional, explicitly enabled provisional curve in m/s: `(8,0), (20,100)` |

WBGT is used once. If no usable WBGT exists, a fresh/reliably mapped official `heat_stress_level.category_value` can supply a categorical fallback: Low=20, Moderate=60, High=90. Neither air temperature/humidity nor official heat category is added on top of WBGT. Heat categories from numeric WBGT use Low below 31, Moderate from 31 to below 33, High at least 33. These category boundaries are from [Meteorological Service Singapore's heat-stress advisory](https://www.weather.gov.sg/wp-content/uploads/2023/07/Heat-Stress-A4-v13.pdf); the continuous score curve and category score numbers are our provisional choices. Official category metadata that disagrees with numeric WBGT produces a warning; WBGT remains authoritative for this component.

Usable PM2.5 takes precedence over PSI, regardless of PSI's magnitude. If PM2.5 is missing/stale/spatially unusable, use usable PSI alone and disclose its 24-hour window. The primary curve uses anchors informed by [NEA's one-hour PM2.5 bands](https://www.haze.gov.sg/), but interpolation, output scores and PSI normalization are engineering choices, not NEA health categories. PM10 is not counted again. These are configured regional measurements, not route-specific pollution estimates. Falling back to PSI or heat categories gives `caution` eligibility because information is coarser.

Wind direction, gusts, headwind/tailwind, route direction and tree-fall hazards are not inferred. Neutral wind means no defensible penalty has been enabled, **not zero physical danger**. Missing/stale/unrepresentative wind still makes the overall assessment incomplete even in neutral mode.

```text
risk = 0.35 * rainfall + 0.35 * heat + 0.25 * air_quality + 0.05 * wind
```

All four components must have usable values; otherwise `risk_score=null`, `risk_level=unknown`, `risk_status=incomplete`. We do not renormalize around missing or zero-weight components. Completeness is usable components / 4, with per-component freshness, source metric/window, station distance, spatial band, selected heat category and warnings. Complete risk levels are low below 40, elevated from 40 to below 70, and high at least 70; these are configurable engineering labels.

## Freshness and spatial uncertainty

Evaluation uses an aware request-time clock, or explicit `as_of` in the independently testable assessor. It recalculates age from `observed_at` against each metric's existing source freshness threshold. It also requires a valid source/unit/window contract, location identity, and observation/fetch timestamps. Future observation, fetch or source-update timestamps cannot contribute before their availability. Persisted `state=fresh` is never accepted as permanent freshness; cache delivery by itself does not invalidate a still-fresh observation.

Station coverage uses the existing `station_distance_km` and Mapping V1 start-point method:

| Distance | Provisional coverage band |
| --- | --- |
| <=1 km | high |
| >1–3 km | moderate |
| >3–5 km | low |
| >5 km | very_low |
| Missing/invalid distance or unsupported mapping | unknown |

These bands indicate coverage, not calibrated measurement accuracy. `max_reliable_station_distance_km=5` is a **confidence threshold**, not necessarily a numerical availability cutoff. With `allow_approximate_station_estimates=true` (default), a fresh, correctly mapped station beyond that threshold can provide an `estimate_status=approximate` component up to the existing `matching.station_max_distance_km` limit (15 km by default). The same score curve applies: distance does not manufacture a new weather value or an arbitrary score penalty. Its warnings explicitly identify the distant station, very-low confidence and absence of measurements along the route. At the mapping limit scoring is allowed; beyond it, or with an unknown distance/mapping, the score remains null. Setting the approximation flag false restores the original strict cutoff.

`RiskComponent.estimate_status` separates supported, approximate and unavailable inputs from its freshness and spatial band. `RiskDataQuality.scored_components` and completeness count all available component scores, including approximations; `reliable_components` counts only scored components within the confidence threshold or supported configured regions. These names denote this engineering policy, not scientifically calibrated reliability. Overall `confidence` is unknown for an incomplete score, very_low for an approximate or simulated estimate, otherwise the worst selected spatial band (regional maps to moderate; categorical fallback is at most moderate). No approximation rescues stale, missing, future-unavailable or invalid-contract inputs.

Configured air-quality regions are reported as `regional`, not assigned a fictitious station distance. Even high start-point coverage does not measure the entire route; zero station rainfall does not establish that the whole route is dry. Synthetic demo source kinds are disclosed and produce caution rather than a claim of verified live conditions.

## Eligibility and blocking

- `eligible`: complete data, no configured blocking condition, no caution condition. This means eligible under this limited policy, not guaranteed safe.
- `caution`: complete but risk >=40, a selected component >=70, low/very-low station coverage, synthetic source data, or categorical heat/PSI fallback.
- `unknown`: incomplete environmental assessment, unless an independently supported blocking rule triggers.
- `blocked`: an enabled numeric rule matches a fresh/reliably mapped observed metric. Can apply even when other components are missing; stale/missing evidence does not trigger a block.

Default `blocking_rules=[]`. No emergency/medical blocking threshold is shipped. To enable a rule, an operator must verify an appropriate policy/source for the intended population/context and configure its `metric`, inclusive `threshold`, `reason`, `policy_source`, and `enabled=true`. Configuration validates presence of supporting text; it cannot authenticate the source or determine that a policy applies. Rules are evaluated independently of risk weighting and personalization. A rule may trigger on an approximate station estimate only when its source/context supports that use and `allow_approximate_estimates=true` is explicitly set on that rule. Default rules require supported evidence within the confidence gate (or supported regional evidence). An otherwise matching approximate input generates a warning instead of an unsupported automatic block. Rules still cannot use stale, missing or future-unavailable values. Tests use clearly labelled synthetic fixture policies, not asserted public safety thresholds.

## Recommendation scoring and fallback

For complete, non-blocked candidates:

```text
relative_difference = abs(route_km - target_km) / target_km
environment = 100 - risk
distance = 100 * max(0, 1 - relative_difference)
accessibility = max(0, 100 - 2 * straight_line_access_km)
                or the same neutral 50 for every route when location is absent
difficulty = 100 * max(0, 1 - abs(predicted_difficulty - target_difficulty) / 4)
recommendation_score = .45*environment + .25*distance
                     + .15*accessibility + .15*difficulty
```

Accessibility retains the existing two-points-per-km penalty; no location or travel distance is invented. Difficulty uses the existing absolute target mismatch, normalized over the 1–5 range. Distance uses the existing absolute mismatch divided by the requested target to prevent short-target mismatches from looking close. Curves/weights, neutral accessibility, access penalty and distance tolerance are configurable.

Each recommendation reports absolute and relative distance differences; >30% mismatch yields a warning, and when all surviving candidates exceed tolerance the Run warns that none reasonably matches. A 4 km route for a 1.2 km target has 2.8 km absolute / 233.33% relative mismatch and distance score zero. Route geometry is never shortened.

**Ordering policy:** complete non-blocked `eligible` and `caution` assessments share one comparison group, sorted by descending weighted score, original baseline rank, then route ID. Confidence and caution are disclosed separately; they do not silently demote every low-confidence route behind every higher-confidence route. This intentionally supersedes Sprint 1's original eligible-before-caution ordering. No confidence penalty or weight change is introduced. Choosing a low-confidence estimate still requires reading its warnings; a higher weighted score is not a safety assurance. Unknown-score fallback follows complete scores, and explicit blocks always take precedence (blocked results are removed from recommendations). Unknowns receive **no weighted score/components**; discovery retains the existing baseline score/order, explicitly labelled `legacy_non_environmental`. Missing data cannot award environmental suitability or promote an unknown route ahead of a known caution route. The authenticated unknown group retains existing difficulty-mismatch reranking with original rank tie-breaking. Complete authenticated groups use the weighted score already incorporating personalized difficulty. Blocked routes are excluded from both recommendation lists and remain visible in catalog/risk data.

## Ranking fields and personalized integration

| Field | Exact meaning |
| --- | --- |
| `score` | Unchanged legacy baseline distance/access/available-probability score; not a final weighted score or percentage |
| `base_recommendation_score` | Personal wrapper alias of `score` |
| `original_base_rank` | One-based original baseline candidate position before risk/personal reordering or blocking; may have gaps after exclusions |
| `recommendation_score` | New normalized weighted score incorporating the request's generic/personal difficulty; null for unknown/blocked assessments |
| `final_rank` | Canonical one-based contiguous position in the returned recommendation list |
| `personalized_rank` | Personal wrapper alias of final_rank; reflects the final risk-aware ordering, not a separate pure difficulty sort |
| `personalized_score` | Legacy negative difficulty mismatch diagnostic; only controls unknown-risk personal fallback, never overrides a complete weighted score |
| `risk_level` | Numerical environmental severity; separate from confidence and eligibility |
| `risk_confidence` | Compact recommendation summary of Run.risks[].risk_data_quality.confidence |
| `eligibility` | Policy state; a caution flag may describe severity or uncertainty, and an explicit block excludes the candidate |

The pipeline and personalized wrapper use the same sort-key implementation. Complete scores already contain personalized difficulty and are not replaced by a second difficulty-only sort. For unknown personal assessments the pipeline performs the existing mismatch fallback before saving the Run, so returned `run.recommendations`, outer `recommendations` and persisted run snapshots have identical order/ranks. Auth, personal calibration, candidate/access filtering and baseline scores remain unchanged.

## Forecast and duration semantics

Risk mode is always `current_observation` in Sprint 1. Prediction results add `prediction_status=forecast_unavailable` when unavailable, mock, or lacking a genuine value, and `forecast_available` only for non-mock available values. A demo probability is not a forecast. Even if a future provider supplies real rainfall probabilities, this version's risk score remains explicitly observation-based; a calibrated forecast-risk adapter is future work. The user's requested horizon and run duration are retained; current observations are not stretched across the future run window or passed off as predicted conditions.

## Synthetic before/after comparison

This is a controlled fixture, not real Singapore weather or model-performance evidence. Both routes are 4 km, target=4 km, predicted/target difficulty=3, no starting location; all observations are fresh and stations 0.5 km from the representative point. PSI is ignored because usable PM2.5 exists. Wind is neutral.

| Synthetic candidate | Rain mm / WBGT degC / PM2.5 ug/m3 | Legacy score/rank | Risk | New score/rank |
| --- | --- | --- | --- | --- |
| a | 10 / 35 / 350 | 100 / 1 (ID tie-break) | 95, caution | 49.75 / 2 |
| b | 0 / 26 / 0 | 100 / 2 | 0, eligible | 92.50 / 1 |

The maximum here is 92.5 because missing location gets neutral accessibility, not invented perfect access. This comparison is executable in `test_risk_changes_ranking_and_preserves_baseline_score`.

## Validation and limits

Tests use synthetic typed observations and temporary storage; test collection redirects the default API data root away from real runtime. Tests cover normalization, zero/missing, heat/air precedence, age/availability, coverage, configurable policy, ranking and personal integration, anonymous/unknown fallback, distance mismatch, determinism, forecast status and additive API compatibility. See [final verification](FINAL_INTEGRATION.md) for current execution results.

No frontend, collector, historical observation CSV, training snapshot, forecasting model, route sampling V2, agent implementation, Docker or Kubernetes changes are part of this sprint. Remaining limits include provisional curves/weights, start-point/region coverage, no future-window modeling, legacy-score display in the unchanged UI, and pre-existing personalization history concurrency/temporal-integrity debt documented in the audit.

## Final integration: dynamic routes and forecast separation

Dynamic routes now reuse `EnvironmentalRiskAssessor`, `RiskPolicy`, and `RiskAwareRanking`. The numeric curves, weights, thresholds, heat fallback and PM2.5/PSI fallback are unchanged. ORS candidate distance/preference checks happen first. Explicitly blocked dynamic routes are excluded from `candidates`; IDs and blocked assessments are returned separately. Unknown assessments have null `recommendation_score` and retain distance/difficulty discovery fallback. The legacy dynamic `score` is preserved as a non-environmental reference; the UI displays shared suitability separately.

Along-route metrics explicitly identify sampling provenance, sample count, matched count and source records. Station quality uses the maximum sample-to-station distance, rather than falsely treating it as a start-point distance. If any sample lacks usable coverage, that component is unscorable. Stale samples make the conservative aggregate stale. The target spacing is 500 m with a maximum of 30 points, so long geometries can have unsampled gaps. Maxima of separate components may occur at different points/times and are conservative engineering aggregates, not a simultaneous measured exposure.

Pollution uses nearest regional centroids at sample points, without polygon containment. It remains coarse regional evidence. Catalog routes retain curated region assignments and start-point station matching. These spatial differences are disclosed in risk warnings and dynamic metric provenance. Neither approach establishes route-wide safety or legal access.

Shared dynamic ordering uses the same environmental/distance/access/difficulty formula as catalog ranking. Since generated candidates start at the requested coordinates, access distance is zero. Personalization then reorders only surviving candidates by difficulty mismatch, with shared rank as tie-breaker. It cannot restore blocks or overwrite the shared score. Invalid supplied sessions return 401; anonymous manual generation remains available.

Live persistence forecasts are supplementary and unvalidated. They never replace current observations, feed a probability into the catalog predictor, or alter risk ranking. Historical forecast risk remains explicitly experimental; its weaker eligibility/availability guarantees have not been promoted into the observation policy. Missing forecast data never becomes zero risk.
