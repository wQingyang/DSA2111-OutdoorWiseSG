# CSV schema

CSV files use UTF-8 with fixed headers. Empty nullable fields represent None, not zero. Timestamps use timezone-aware ISO8601; collectors normalize source times to UTC. Numeric values and categories occupy separate columns.

## locations.csv

Location: `data/runtime/locations.csv`. Column order follows the `Location` contract.

| Field | Python type |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| name | `<class 'str'>` |
| location_type | `Literal['station', 'region']` |
| lon | `<class 'float'>` |
| lat | `<class 'float'>` |
| source_kind | `Literal['live', 'demo']` |
| metadata_updated_at | `<class 'pydantic.types.AwareDatetime'>` |

## environment_observations.csv

Location: `data/runtime/environment_observations.csv`. Column order follows the `EnvironmentObservation` contract.

| Field | Python type |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| observed_at | `<class 'pydantic.types.AwareDatetime'>` |
| source_updated_at | `pydantic.types.AwareDatetime | None` |
| fetched_at | `<class 'pydantic.types.AwareDatetime'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| value | `float | None` |
| category_value | `str | None` |
| unit | `<class 'str'>` |
| aggregation_window | `<class 'str'>` |
| source_kind | `Literal['live', 'demo']` |
| raw_value | `float | None` |
| raw_unit | `str | None` |
| revision | `<class 'int'>` |
| first_fetched_at | `pydantic.types.AwareDatetime | None` |

## environment_observation_versions.csv

Location: `data/runtime/environment_observation_versions.csv`. Column order follows the `EnvironmentObservation` contract.

| Field | Python type |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| observed_at | `<class 'pydantic.types.AwareDatetime'>` |
| source_updated_at | `pydantic.types.AwareDatetime | None` |
| fetched_at | `<class 'pydantic.types.AwareDatetime'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| value | `float | None` |
| category_value | `str | None` |
| unit | `<class 'str'>` |
| aggregation_window | `<class 'str'>` |
| source_kind | `Literal['live', 'demo']` |
| raw_value | `float | None` |
| raw_unit | `str | None` |
| revision | `<class 'int'>` |
| first_fetched_at | `pydantic.types.AwareDatetime | None` |

## route_source_mapping.csv

Location: `data/runtime/route_source_mapping.csv`. Column order follows the `RouteSourceMapping` contract.

| Field | Python type |
|---|---|
| route_id | `<class 'str'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| source | `<class 'str'>` |
| location_id | `str | None` |
| source_kind | `Literal['live', 'demo']` |
| match_method | `<class 'str'>` |
| station_distance_km | `float | None` |
| representative_lon | `<class 'float'>` |
| representative_lat | `<class 'float'>` |
| mapped_at | `<class 'pydantic.types.AwareDatetime'>` |

## route_environment_latest.csv

Location: `data/runtime/route_environment_latest.csv`. Column order follows the `RouteMetric` contract.

| Field | Python type |
|---|---|
| route_id | `<class 'str'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| value | `float | None` |
| category_value | `str | None` |
| unit | `<class 'str'>` |
| aggregation_window | `<class 'str'>` |
| source | `<class 'str'>` |
| location_id | `str | None` |
| location_name | `str | None` |
| source_kind | `Literal['live', 'demo']` |
| delivery | `Literal['live', 'cache', 'demo', 'unavailable']` |
| state | `Literal['fresh', 'stale', 'missing']` |
| match_method | `<class 'str'>` |
| station_distance_km | `float | None` |
| observed_at | `pydantic.types.AwareDatetime | None` |
| source_updated_at | `pydantic.types.AwareDatetime | None` |
| fetched_at | `pydantic.types.AwareDatetime | None` |
| as_of | `<class 'pydantic.types.AwareDatetime'>` |
| revision | `int | None` |
| reason | `<class 'str'>` |

## ingestion_runs.csv

Location: `data/runtime/ingestion_runs.csv`. Column order follows the `IngestionRun` contract.

| Field | Python type |
|---|---|
| run_id | `<class 'str'>` |
| source | `<class 'str'>` |
| source_kind | `Literal['live', 'demo']` |
| started_at | `<class 'pydantic.types.AwareDatetime'>` |
| finished_at | `<class 'pydantic.types.AwareDatetime'>` |
| status | `Literal['success', 'failed', 'skipped']` |
| attempts | `<class 'int'>` |
| received_records | `<class 'int'>` |
| inserted_records | `<class 'int'>` |
| revised_records | `<class 'int'>` |
| unchanged_records | `<class 'int'>` |
| error | `<class 'str'>` |

## Keys and History

- `locations`: source + location_id + source_kind. Stations with identical IDs from different APIs must remain separate.
- `environment_observations`: source + location_id + observed_at (the same instant, regardless of timezone representation) + metric + aggregation_window + source_kind. Repeated collection refreshes fetched_at without appending duplicate observations. Upstream value or updatedTimestamp corrections update the existing row and increment revision.
- `environment_observation_versions`: observation key + revision. Retains previous and current revisions, including first_fetched_at for each version, to support as_of queries. Do not delete this history.
- `route_source_mapping` and `route_environment_latest`: current materialized views keyed by route and metric, including source_kind. Each refresh replaces these views. Historical queries reconstruct results from observation versions rather than reading the latest view.
- `ingestion_runs`: one run_id log entry per source collection attempt, including received, inserted, revised, and unchanged record counts and failure details. Sources skipped by --due do not generate log entries.
- `routes.csv` and GeoJSON files remain in data/catalog with their original formats.

## Historical Query Semantics

An as_of query selects the latest observation with observed_at <= as_of whose revision was first fetched by that time. When the source supplies updatedTimestamp, it must also be <= as_of. Later corrections are not exposed to earlier queries.

The locations table is a current catalog, not a complete historical geography catalog. Exact historical matching after station moves or renaming is not implemented. Individual fetch-time refreshes for unchanged observations are not retained as separate versions, so historical delivery labels may conservatively report cache. Observation values and revisions do not look ahead.

## Writer and Recovery

All CSV I/O belongs to the repository. A thread RLock and cross-process flock serialize writers for the same storage path. Writes use temporary files in the destination directory, fsync, and os.replace.

Multi-file updates first persist a pending transaction journal and then replace each file atomically. Repository initialization replays an interrupted journal. This is not a single operating-system atomic commit across multiple files. Service readers use the same lock; external applications reading CSV directly do not have that guarantee. Use local storage. This adapter does not claim full database transaction guarantees on network filesystems or sudden power loss.

Predictions are stored separately in data/runtime/predictions_latest.json. latest_run.json holds a combined pipeline snapshot. The environmental observation table does not accept future predictions. If the legacy observations.csv exists, its rainfall records are migrated once and the original file is retained for audit.
