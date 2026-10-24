# Haoyun — Work Log

## Responsibilities

- Mapping: Compare station matching based on the route start, route end, and sampling along the route.
- Demo validation: Prepare and validate different demonstration scenarios.
- Visualisation: Prepare figures for the final report and presentation.

## Baseline

- Date: 2026-10-24
- Current branch: haoyun/mapping-demo-validation
- Commit ID: T79dc7f01d586341d9b451c75d123e1f89a61befa
- Application URL: http://127.0.0.1:8000/
- Data mode: Demo (synthetic observations)

### Confirmed

- The homepage loads successfully.
- The application loads 12 predefined routes and displays the top three by default.
- A dynamic route generation tab is available.
- Route cards display Shared Rank, Recommendation Score, Environmental Risk, and Generic Difficulty.
- Environmental Details display the station or region, distance, timestamps, and matching method.
- Predefined routes currently use `nearest_available_station_start_point_v1`.

### Pending Validation

- Selecting a route highlights the corresponding route on the map.
- Changing the target distance and starting location updates the results correctly.
- View All expands and collapses correctly.
- Personalised recommendations work for logged-in users.
- Switching between Current and Historical contexts works correctly.
- Dynamic route generation and error messages work correctly.

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

- Complete the frontend and account-flow validations listed under Pending Validation above.
- Review route geometries still marked `candidate_requires_visual_review` before treating them as approved routes.
- Keep production integration separate until the team agrees on along-route aggregation, coverage metadata, and risk-module compatibility.
