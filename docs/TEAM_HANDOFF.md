# Six-Person Ownership and Integration

The following ownership boundaries are a suggested allocation. 

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
