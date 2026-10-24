# Haoyun — Work Log

## Responsibilities

- Mapping: Compare station matching based on the route start, route end and sampling along the route.
- Demo validation: Prepare and validate the main demonstration workflows.
- Visualisation: Prepare figures and screenshots for the final report and presentation.

## Baseline

- Baseline date: 2026-10-24
- Working branch: `haoyun/mapping-demo-validation`
- Baseline source commit: `79dc7f01d586341d9b451c75d123e1f89a61befa`
- Application URL: http://127.0.0.1:8000/
- Manual demonstration data mode: Demo (synthetic observations)

The application loads 12 predefined routes and displays the top three by default. Route cards include shared ranking, recommendation score, environmental risk and difficulty information.

Predefined routes used `nearest_available_station_start_point_v1` during validation. The independent mapping experiment did not change production matching or recommendation behaviour.

## Mapping Experiment

### Methods

Compared three station-matching methods using the same observation snapshot and timezone-aware assessment time:

1. Nearest usable station to the route start.
2. Nearest usable station to the route end.
3. Nearest usable station at sample points approximately every 500 metres along the route.

Recorded sample counts, matched counts, spatial coverage, fresh coverage, distinct station counts, matching distances and matched environmental values.

Regional PM2.5, PSI and PM10 assignments were kept separate from station-based metrics. Wind direction was excluded from arithmetic value comparisons.

### Validation

- Focused experiment tests: 6 passed.
- Full Python suite at implementation: 129 passed.
- Saved summary results were checked against the per-sample records.
- Each experiment output contains 1,317 sample/assignment rows and 288 summary rows across 12 routes.
- The sample rows include repeated assignments of the same station; they are not independent observations.

### Synthetic Demo Experiment

The synthetic experiment demonstrated that the comparison workflow could run and identify routes matching multiple stations.

Some observations were stale at the assessment time. Synthetic results were used to validate program behaviour, not actual station coverage or environmental accuracy.

Files:

- [Demo analysis](mapping-results/demo/analysis.md)
- [Demo summary](mapping-results/demo/summary.csv)
- [Demo per-sample records](mapping-results/demo/per_sample.csv)

### Initial Live Collection Attempt

All eight sources failed with connection errors and supplied no new observations. The experiment therefore used previously saved live data, which was entirely stale at assessment time.

This failed-refresh result was retained separately from the successful retry.

Files:

- [Collection report](mapping-results/live/collection-report.md)
- [Stored-live summary](mapping-results/live/summary.csv)
- [Stored-live per-sample records](mapping-results/live/per_sample.csv)

### Successful Live-Retry Snapshot

Assessment time:

- Singapore: 24 Oct 2026, 23:09:41 SGT
- UTC: `2026-10-24T15:09:41.280461+00:00`

Findings:

- All 12 catalog routes have coincident first and last coordinates. Start-point and end-point matching therefore produced identical results.
- Along-route sampling matched multiple stations in 35 route/metric combinations.
- Bedok Reservoir matched three rainfall stations: S129, S300 and S84.
- All 1,113 along-route station sample assignments were fresh and within the configured 15 km matching limit.
- Start-point and end-point station assignments were also fresh, as were the 36 separate regional assignments.
- Along-route matched-sample means differed from start-point values in 17 numeric route/metric comparisons.
- All matched rainfall values were zero, so rainfall-value differences could not be demonstrated in this snapshot.

Files:

- [Live-retry analysis](mapping-results/live-retry/analysis.md)
- [Live-retry summary](mapping-results/live-retry/summary.csv)
- [Live-retry per-sample records](mapping-results/live-retry/per_sample.csv)
- [Full mapping study](mapping-study.md)

### Interpretation and Limits

The experiment supports the feasibility of along-route multi-station matching for the assessed snapshot.

It does not establish measurement accuracy, route safety or conditions at every point between samples. Shorter station distance does not by itself prove better environmental representation.

Start-point and end-point coverage each concern one representative point. They are not equivalent to whole-route sampled coverage.

Along-route means and maxima summarise values assigned to samples; they are not ground-truth measurements taken along the route.

Production integration remains separate and requires agreement on aggregation, coverage metadata and risk-module compatibility. Catalog route geometries retain their existing visual-review status.

## Manual Demo Validation

- Test date: 2026-10-24
- Data mode: Demo (synthetic observations)
- Method: Manual browser testing
- Additional D05 screenshot captured: 2026-10-25

| ID | Test | Expected result | Actual result | Status |
|---|---|---|---|---|
| D01 | Select two routes using View Route | The map focuses on or highlights the corresponding route each time. | Both selected routes corresponded correctly to their map display. | Pass |
| D02 | Change target distance from 4 km to 8 km and compare again | Results reload successfully and distance-match explanations reflect the updated target. | At 4 km, Marina Bay waterfront loop ranked first. At 8 km, MacRitchie Reservoir forest loop ranked first. Both requests loaded successfully, and the displayed distance differences were correct. | Pass |
| D03 | Expand and collapse the route list | View All displays all 12 routes, and collapsing restores the top three. | Both View All and collapse worked correctly. | Pass |
| D04 | Select NUS as the preset starting location with a 5 km access limit | A start marker appears and all returned routes have access distances within 5 km. | The NUS start marker appeared. Three routes were returned: West Coast (1.76 km), Singapore Botanic Gardens (4.71 km), and Bukit Timah Rail Corridor (2.85 km). All access distances were within the limit. | Pass |
| D05 | Reduce the NUS access limit to 0.1 km | No routes are returned if none meet the strict access limit. | No matching routes were returned. The page explained that the 0.1 km limit had not been relaxed. | Pass |
| D06 | Restore Anywhere in Singapore and compare again | Routes reappear, the start marker is removed, the access limit is disabled, and the empty-result message clears. | All expected behaviours were confirmed after restoring Anywhere mode. | Pass |
| D07 | Compare the same route across two synthetic test users with identical preferences | Shared results remain unchanged, while personalised difficulty and ranking reflect each user's history. | For Botanic Gardens, both users had Recommendation Score 74.0, Environmental Risk 11.9, Shared Rank #5 and Generic Difficulty 2.5. Runner 1 had personalised difficulty 3.0, mismatch 0.0 and personal rank #1; Runner 2 had 2.6, 0.4 and #7, respectively. | Pass |
| D08 | Load historical recommendations while logged in as test_runner_2 | Historical results load and display shared and personalised fields with an explicit historical label. | Historical comparison loaded successfully. Cards displayed shared rank, personal rank, recommendation score, environmental risk, generic difficulty, personalised difficulty and target mismatch, with a historical baseline label. | Pass |
| D09 | Expand and collapse historical recommendations | The list switches correctly between all 12 routes and the top three. | View All and collapse both worked correctly in Historical mode. | Pass |
| D10 | Switch from Historical to Current and back | Each context loads correctly without retaining cards from the previous context. | Compare routes restored Current conditions and demo cards. Historical comparison then loaded successfully again. | Pass |

These results cover the recorded demonstration scenarios. They do not establish complete system correctness or validate the internal ranking algorithm in every case.

Dynamic route configuration and functional validation are owned by the dynamic-routing developer and are outside this validation scope.

## Figure and Screenshot Evidence

All paths below are relative to this document.

### Baseline

| Figure | Description |
|---|---|
| [Baseline dashboard](figures/baseline-demo-dashboard.png) | Initial Demo dashboard showing the map, preferences and recommendation cards. The screenshot uses a 3.5 km target and 60-minute duration; it is a baseline illustration, not evidence for the D02 distance comparison. |

### Mapping Experiment — Synthetic Demo Data

| Figure | Description |
|---|---|
| [Demo matching map](figures/demo-rainfall-matching-map.png) | Start-point and along-route rainfall station matching for Singapore Botanic Gardens using synthetic observations. |
| [Demo station distances](figures/demo-rainfall-station-distance.png) | Mean and maximum station-to-sample distances for the three methods across seven station-based metrics. Despite the filename, this figure is not limited to rainfall. |
| [Demo fresh coverage](figures/demo-fresh-coverage.png) | Along-route fresh coverage by route and metric, showing the freshness limitations of the saved synthetic snapshot. |

### Mapping Experiment — Live Observation Snapshot

Assessment time: 24 Oct 2026, 23:09:41 SGT.

| Figure | Description |
|---|---|
| [Live matching map](figures/live-rainfall-matching-map.png) | Bedok Reservoir route samples matched to three rainfall stations: S129, S300 and S84. |
| [Live station distances](figures/live-rainfall-station-distance.png) | Mean and maximum station-to-sample distances for the three methods across seven station-based metrics. Despite the filename, this figure is not limited to rainfall. |
| [Live fresh coverage](figures/live-fresh-coverage.png) | All along-route sample matches were fresh in this snapshot. This does not establish measurement accuracy or continuous coverage between samples. |

### Manual Demo Screenshots

| Test | Screenshot | Evidence |
|---|---|---|
| D04 | [NUS start marker](figures/nus-access-5km-map.png) | NUS preset selected, start marker displayed and 5 km access limit configured. |
| D04 | [First two matching routes](figures/nus-access-5km.png) | West Coast and Singapore Botanic Gardens access distances of 1.76 km and 4.71 km, both within 5 km. |
| D04 | [Third matching route](figures/nus-access-5km-third-route.png) | Bukit Timah Rail Corridor access distance of 2.85 km, within 5 km. |
| D05 | [No matching routes](figures/nus-access-0.1km-empty.png) | NUS with a 0.1 km access limit returns zero routes and an explanatory message. Evidence recaptured on 25 Oct 2026. |
| D07 | [Test runner 1 — Current](figures/test-runner-1-current.png) | Botanic Gardens has shared rank #5, personalised difficulty 3.0, mismatch 0.0 and personal rank #1. |
| D07 | [Test runner 2 — Current](figures/test-runner-2-current.png) | The same route retains its shared values, while personalised difficulty is 2.6, mismatch is 0.4 and personal rank is #7. |
| D08 | [Historical first two routes](figures/test-runner-2-historical.png) | Historical results display shared and personalised fields with an explicit historical label. |
| D08 | [Historical third route](figures/test-runner-2-historical-third-route.png) | Additional historical card and the View All button. |

### Evidence Scope

- D01–D03, D06, D09 and D10 are supported by the recorded manual test results; no dedicated before/after screenshot pairs are included.
- Static screenshots show page states. Interactive behaviours such as switching, expanding and collapsing are documented in the manual test table.
- Mapping figures show independent experiment results, not changes to production matching.

## Deliverables and Handoff

Completed materials:

- Independent comparison script: `scripts/compare_route_mapping.py`
- Analysis and plotting script: `scripts/analyze_route_mapping.py`
- Experiment tests: `tests/test_route_mapping_experiment.py`
- [Mapping study](mapping-study.md)
- Saved experiment CSVs and analyses under `mapping-results/`
- Figures and screenshots under `figures/`
- [Demonstration script](demo-script.md)

Remaining handoff actions:

- Rehearse the demonstration using `demo-script.md`.
- Use the relevant findings and figures in the final report and presentation.
- Coordinate any production integration separately with the relevant module owners.