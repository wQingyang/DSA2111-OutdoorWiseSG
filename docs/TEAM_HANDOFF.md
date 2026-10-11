# Six-Person Ownership and Integration

The following ownership boundaries are a suggested allocation. Replace owner numbers with team members' names. Owner 1 is responsible for database and pipeline integration. Shared interface changes require team review.

| Owner | Primary files and directories | Interface and deliverables |
|---|---|---|
| 1: Database and pipeline integration | storage, pipeline, bootstrap, contracts | Repository adapter, observation keys and revisions, get_route_environment, module composition, continuous collection worker, integration verification |
| 2: Environmental ingestion | collectors, source configuration in config/environment.toml | collect() -> (CollectionBatch, attempts), source/unit/window contracts, recorded API fixtures |
| 3: Routes and spatial data | data/catalog, geometry strategy in services | Stable route_id values, reviewed regional mappings, future GeoJSON sampling |
| 4: Rainfall prediction | modules/predictor.py | predict(conditions, horizon_min) -> one Prediction per route; inject the shared reader for full environment features |
| 5: Environmental risk, recommendations, and agent | modules/risk.py, modules/recommender.py, agent | assess(environments) -> EnvironmentRisk; rank(...) -> Recommendation; explanations grounded in structured tool outputs |
| 6: Frontend and API presentation | frontend, api | Consume the current HTTP contracts; display nulls, state, delivery, provenance, and timestamps; preserve the map and forms |

## Fixed Contracts

- `get_route_environment(route_id, as_of=None) -> RouteEnvironment` is the shared consumer interface. as_of must include a timezone; omission means the current time.
- `EnvironmentCollector.collect() -> tuple[CollectionBatch, int]` does not write files. Transport failures use CollectionFailure. Upstream field changes fail that source rather than being reported as successful collection.
- `EnvironmentRepository`, `RouteEnvironmentReader`, `Predictor`, `EnvironmentRiskAssessor`, and `Recommender` are defined in contracts/ports.py.
- Predictor retains the existing Conditions input for compatibility. Inject a reader during construction, as shown in templates/module_template.py, to obtain additional metrics. Outputs must include generated_at, horizon_min, source, is_mock, and status. Unknown probabilities remain None. Live mode rejects mock forecasts.
- The risk assessor currently returns unavailable. Official heat stress is displayed as a source observation, not presented as the team's comprehensive risk model.
- BaselineRecommender retains the original distance and rainfall rules. Team implementations may inject the reader to use additional environmental metrics; the current baseline does not use every new metric.
- Agent tools consume validated data and module outputs. The existing LLM tool loop is retained, but no real provider call was verified without credentials. Inspect the demo assistant's fixed sequence through its trace.

## Collaboration Rules

Edit files within your ownership boundary. Propose shared interface additions in contracts and schema documentation first, then obtain integration-owner review.

Business modules must not read or write CSV directly, independently request environmental APIs, fill missing measurements with zero, write forecasts into observation history, or interpret current observations as future probabilities.

New collectors require recorded official response fixtures and unit validation. Connect new modules in bootstrap using the supplied templates, then verify the pipeline integration. Run `python -m pytest -q` to check import ownership and key data behavior.
