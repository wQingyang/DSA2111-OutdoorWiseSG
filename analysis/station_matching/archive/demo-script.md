> Historical record of the October 2026 experiment and demo. UI controls and development assignments below are not current operating instructions; use the repository README.

# OutdoorWise Demonstration Script

## Preparation

- Start the application in Demo mode.
- Open http://127.0.0.1:8000/.
- Use the existing-route recommendations tab.
- Keep both synthetic test accounts available.
- Clearly distinguish synthetic demo observations from the saved live mapping experiment.

## 1. Route Recommendations

Set the preferences to:
- Target distance: 4 km
- Duration: 30 minutes
- Start time: Now
- Starting location: Anywhere in Singapore
- Target difficulty: Comfortable

Click Compare routes.

Explain the Recommendation Score, Environmental Risk and Generic Difficulty. Select a route using View Route, then demonstrate View All and collapse.

Change the target distance to 8 km and compare again. Explain that the recommendations and distance-match descriptions update.

## 2. Starting Location and Access Limit

Restore the target distance to 4 km.

Select NUS as the preset starting location and set the maximum access distance to 5 km. Show the start marker and the straight-line access distances.

Reduce the limit to 0.1 km to demonstrate the no-matching-routes state.

Restore Anywhere mode and compare again.

## 3. Personalised Recommendations

Use identical preferences for both synthetic test users.

For Singapore Botanic Gardens, the recorded Current demo results were:

| Field | test_runner_1 | test_runner_2 |
|---|---:|---:|
| Recommendation Score | 74.0 | 74.0 |
| Environmental Risk | 11.9 | 11.9 |
| Shared Rank | 5 | 5 |
| Generic Difficulty | 2.5 | 2.5 |
| Personalised Difficulty | 3.0 | 2.6 |
| Difficulty Difference | 0.0 | 0.4 |
| Personal Difficulty-Match Rank | 1 | 7 |

Explain that shared results remain consistent while personalised difficulty and ranking reflect user history. These are recorded results; confirm the displayed values during rehearsal.

## 4. Historical Context

Click Compare historical forecasts.

Explain that this is a historical replay with baseline assumptions, rather than current weather.

Demonstrate View All and collapse, then return to Current using Compare routes.

## 5. Mapping Experiment Findings

Show the saved live matching map and comparison figures.

Explain:
- All 12 catalog routes have coincident start and end coordinates, so endpoint matching gives the same result as start-point matching.
- Along-route sampling matched multiple stations in 35 route/metric combinations.
- Bedok Reservoir matched three rainfall stations.
- All sampled station matches were fresh and within the configured distance limit in the assessed live snapshot.
- Along-route numeric means differed from start-point values in 17 comparisons.
- All matched rainfall values were zero in that snapshot.
- These results demonstrate feasibility, not measurement accuracy.

## Scope and Limitations

- The mapping experiment is independent of the production recommendation flow.
- Production integration requires agreement on aggregation, coverage metadata and risk-module compatibility.
- Dynamic route configuration and functional validation belong to the dynamic-routing developer.
- Manual validation covered D01–D10; it does not establish complete system correctness.