# Haoyun — Work Log

## Responsibilities

- Mapping: Compare station matching based on the route start, route end, and sampling along the route.
- Demo validation: Prepare and validate different demonstration scenarios.
- Visualisation: Prepare figures for the final report and presentation.

## Baseline

- Date: 2026-10-24
- Current branch: haoyun/mapping-demo-validation
- Commit ID: 79dc7f01d586341d9b451c75d123e1f89a61befa
- Application URL: http://127.0.0.1:8000/
- Data mode: Demo (synthetic observations)

### Confirmed

- The homepage loads successfully.
- The application loads 12 predefined routes and displays the top three by default.
- A dynamic route generation tab is available.
- Route cards display Shared Rank, Recommendation Score, Environmental Risk, and Generic Difficulty.
- Environmental Details display the station or region, distance, timestamps, and matching method.
- Predefined routes currently use `nearest_available_station_start_point_v1`.

### Manual Validation Status

- D01–D10 passed manual browser validation. Details are recorded below.
- Dynamic route configuration and functional validation are owned by the dynamic-routing developer.

## Mapping Experiment Plan

Compare the following methods using the same observation snapshot and assessment time:

1. Start-point matching.
2. End-point matching.
3. Matching at sample points spaced approximately 500 metres along the route.

Record:

- Number of sample points and successfully matched points.
- Matching coverage.
- Number of distinct matched stations.
- Mean and maximum matching distances.
- Environmental values.
- Data freshness and availability.

## Observations and Issues

- The West Coast route reports a selected station approximately 8.09 km from the route start. This is a potential case for comparing matching methods.
- Synthetic demo data can validate application behaviour. Actual station coverage requires a separate experiment using live observations.

## Mapping Experiment Status

### Completed

- Recorded the working branch and repository commit in the baseline notes and retained the baseline dashboard screenshot at `docs/haoyun/figures/baseline-demo-dashboard.png`.
- Implemented and tested the independent station-matching comparison for start, end, and approximately 500 m along-route samples. The focused tests passed (6 tests); the full suite passed (129 tests).
- Executed the comparison against the saved synthetic demo snapshot and the saved live-retry snapshot. Results, per-sample records, analyses, and figures remain under `docs/haoyun/mapping-results/` and `docs/haoyun/figures/`.
- Verified the saved live-retry summary against its per-sample records. The recorded assessment time is 24 Oct 2026, 23:09:41 SGT (2026-10-24T15:09:41.280461+00:00 UTC).
- Audited the 12 catalog geometries: every first and last coordinate is coincident, which explains the identical start/end matches in the experiment.

### Remaining tasks

- Rehearse the demonstration using docs/haoyun/demo-script.md.
- Prepare the completed evidence for team review.
- Production integration remains separate and requires agreement on aggregation, coverage metadata and risk-module compatibility.
- Route geometries retain their existing visual-review status; this experiment does not approve them for navigation.


## Manual Demo Validation

- Test date: 2026-10-24
- Data mode: Demo (synthetic observations)
- Validation method: Manual browser testing

| ID | Test | Expected result | Actual result | Status |
|---|---|---|---|---|
| D01 | Select two routes using View Route | The map focuses on or highlights the corresponding route each time. | Both selected routes corresponded correctly to their map display. | Pass |
| D02 | Change target distance from 4 km to 8 km and compare again | Results reload successfully and distance-match explanations reflect the updated target. | At 4 km, Marina Bay waterfront loop ranked first. At 8 km, MacRitchie Reservoir forest loop ranked first. Both requests loaded successfully, and the displayed distance differences were correct. | Pass |
| D03 | Expand and collapse the route list | View All displays all 12 routes, and collapsing restores the top three. | Both View All and collapse worked correctly. | Pass |
| D04 | Select NUS as the preset starting location with a 5 km access limit | A start marker appears and all returned routes have access distances within 5 km. | The NUS start marker appeared. Three routes were returned: West Coast (1.76 km), Singapore Botanic Gardens (4.71 km), and Bukit Timah Rail Corridor (2.85 km). All access distances were within the limit. | Pass |
| D05 | Reduce the NUS access limit to 0.1 km | No routes are returned if none meet the strict access limit. | No matching routes were returned after applying the 0.1 km limit. | Pass |
| D06 | Restore Anywhere in Singapore and compare again | Routes reappear, the start marker is removed, the access limit is disabled, and the empty-result message clears. | All expected behaviours were confirmed after restoring Anywhere mode. | Pass |
| D07 | Compare the same route across two synthetic test users with identical preferences | Shared results remain unchanged, while personalised difficulty and difficulty-match ranking reflect each user's history. | For Botanic Gardens, both users had Recommendation Score 74.0, Environmental Risk 11.9, Shared Rank #5 and Generic Difficulty 2.5. Runner 1 had personalised difficulty 3.0, mismatch 0.0 and personal rank #1; Runner 2 had 2.6, 0.4 and #7, respectively. | Pass |
| D08 | Load historical recommendations while logged in as test_runner_2 | Historical results load and display shared and personalised recommendation fields with an explicit historical label. | Historical comparison loaded successfully. Cards displayed shared rank, personal rank, recommendation score, environmental risk, generic difficulty, personalised difficulty and target mismatch, with a historical baseline label. | Pass |
| D09 | Expand and collapse historical recommendations | The list switches correctly between all 12 routes and the top three. | View All and collapse both worked correctly in Historical mode. | Pass |
| D10 | Switch from Historical to Current and back | Each context loads correctly without retaining cards from the previous context. | Compare routes restored Current conditions and demo cards. Historical comparison then loaded successfully again. | Pass |