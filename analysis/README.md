# Report analyses and experiments

This directory is the central location for supporting analyses, experiments,
data quality assessments, and performance evaluations for the DSA2111 final
report and presentation. These are independent of application startup and do not
change production matching, risk policies, or prediction behavior.

| Analysis | Description | Report relevance |
|---|---|---|
| [Data Freshness](data_freshness/README.md) | Observation age, collection timestamps, and data freshness assessment | Data Governance / Data Quality |
| [Station Matching](station_matching/README.md) | Comparison of V1 single-station and V2 route-level station matching | Methodology / Model Design |
| [Risk and Catalog Evaluation](risk_model/README.md) | Controlled risk/eligibility checks and archived catalog ranking comparisons | Environmental Risk / Recommendation Evaluation |

Future contributors may add independent subdirectories for risk model evaluation,
prediction model performance, route coverage analysis, data quality checks, and
system performance benchmarks. Create a directory when there is work to include;
empty placeholders are unnecessary.

Each analysis should contain its own README, reproducible scripts, results, and
figures. Document input paths, dependencies, timestamp/metric definitions, methods,
limitations, and reproduction commands. Distinguish recorded, synthetic, and live
evidence. Preserve existing results and use temporary output directories when
validating a saved experiment. Never point a repository-initializing experiment at
protected operational storage; use a separate copied data root when required.

The station-matching archive also preserves historical application demo notes and
linked screenshots as provenance; these are not current operating instructions.
Protected research training code and frozen artifacts remain under `prediction/`,
and production evaluation modules remain under `outdoorwise/`. This index does not
relocate runtime dependencies into the report-analysis area.
