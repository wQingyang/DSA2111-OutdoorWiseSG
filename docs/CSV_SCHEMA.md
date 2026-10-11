# CSV Schema — Storage Version 3

All CSV files use UTF-8 with fixed headers. Empty nullable fields represent None, not zero. Numeric measurements and categories occupy separate columns.

## Timestamp Contract

Every CSV time column uses `YYYY-MM-DDTHH:MM:SS` in **Asia/Singapore**. For example, `2026-10-05T03:38:28.869141Z` is stored as `2026-10-05T11:38:28`. No fractional seconds, Z, or offset suffix is stored. The timezone is defined by this schema and data/runtime/csv_storage_metadata.json, not by the machine timezone.

The repository restores timezone information on read and converts aware timestamps on write. Source parsers and HTTP interfaces continue to require timezone-aware times. An offset-free CSV time must never be interpreted as UTC. The same rule applies to observations, revisions, station metadata, mapping and summary times, and ingestion logs. Nullable missing times remain empty.

Persistence uses second precision, discarding subsecond fractions. Observation keys also use second precision. History queries have second-level availability resolution.

## Observation Categories

| Category | Current observations | Revision history | Metrics |
|---|---|---|---|
| Weather | weather_observations.csv | weather_observation_versions.csv | rainfall, wind_speed, wind_direction, air_temperature, relative_humidity |
| Air quality | air_quality_observations.csv | air_quality_observation_versions.csv | pm25, psi, pm10 |
| Heat stress | heat_stress_observations.csv | heat_stress_observation_versions.csv | wbgt, heat_stress_level |

Each table uses a long format: one metric per row. Aggregation windows remain independent of polling intervals. Station IDs remain source-specific; air-quality regions are not weather stations. locations.csv is a unified source directory.

## locations.csv

Location: `data/runtime/locations.csv`. Column order follows the internal `Location` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| name | `<class 'str'>` |
| location_type | `Literal['station', 'region']` |
| lon | `<class 'float'>` |
| lat | `<class 'float'>` |
| source_kind | `Literal['live', 'demo']` |
| metadata_updated_at | `<class 'pydantic.types.AwareDatetime'>` |

## weather_observations.csv

Location: `data/runtime/weather_observations.csv`. Column order follows the internal `EnvironmentObservation` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

## air_quality_observations.csv

Location: `data/runtime/air_quality_observations.csv`. Column order follows the internal `EnvironmentObservation` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

## heat_stress_observations.csv

Location: `data/runtime/heat_stress_observations.csv`. Column order follows the internal `EnvironmentObservation` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

## weather_observation_versions.csv

Location: `data/runtime/weather_observation_versions.csv`. Column order follows the internal `EnvironmentObservation` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

## air_quality_observation_versions.csv

Location: `data/runtime/air_quality_observation_versions.csv`. Column order follows the internal `EnvironmentObservation` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

## heat_stress_observation_versions.csv

Location: `data/runtime/heat_stress_observation_versions.csv`. Column order follows the internal `EnvironmentObservation` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

Location: `data/runtime/route_source_mapping.csv`. Column order follows the internal `RouteSourceMapping` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

Location: `data/runtime/route_environment_latest.csv`. Column order follows the internal `RouteMetric` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

Location: `data/runtime/ingestion_runs.csv`. Column order follows the internal `IngestionRun` contract. The datetime fields below use the CSV timestamp encoding defined above, rather than the internal aware datetime representation.

| Field | Internal Python type |
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

locations uses source + location_id + source_kind. Stations with identical IDs from different sources remain distinct.

Each category observation table uses source + location_id + observed_at (same instant at second precision) + metric + aggregation_window + source_kind. Repeated collection refreshes fetched_at without adding a duplicate. Source corrections increment revision and update the current record. The matching category version table uses the observation key + revision and retains each revision's first_fetched_at.

Current observation tables contain all collected observation timestamps, not just the latest timestamp. Revision tables track changes to those observations; they are not separate forecast tables.

route_source_mapping and route_environment_latest are current views keyed by route and metric, including source_kind. Historical queries reconstruct observations from all three revision tables. ingestion_runs records actual source attempts; --due skips do not create log rows.

## Historical Queries

A revision must have observed_at and first_fetched_at at or before as_of. Where supplied, source_updated_at must also be at or before as_of. Later revisions do not appear in earlier queries. The locations directory remains current metadata rather than a complete historical geography catalog. Unchanged fetch refreshes are not stored as separate revisions, so historical delivery labels may conservatively report cache.

## Initialization and Recovery

Repository initialization creates any missing current tables with their canonical headers and replays pending writes using only the current table registry.

All CSV I/O remains in the repository. Thread RLock and cross-process flock serialize writers; each file uses a same-directory temporary file, fsync, and atomic replacement. A pending journal supports interrupted multi-file replay. This is not a single operating-system atomic transaction across files. Direct external CSV readers do not share the repository lock. Local storage is recommended.

## Operational Files

collection_worker.json stores the last worker report, not observations. csv_storage_metadata.json declares the timestamp convention and table mapping. predictions_latest.json remains separate from observations. Internal JSON snapshots and HTTP responses retain timezone-aware timestamps. The worker lease is separate from the short CSV writer lock; source cooldowns are recovered from ingestion logs.
