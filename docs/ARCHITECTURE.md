# Module Boundaries

```mermaid
flowchart TD
    C["8 independent collectors"] --> S["Typed batch validation"]
    S --> R["CSV repository and revision history"]
    R --> E["Route environment service"]
    E --> P["Pipeline: forecasts and risk modules"]
    E --> A["Agent evidence tools"]
    P --> F["Existing frontend and recommendations"]
    A --> F
```

bootstrap.py is the only composition root. contracts defines schemas and protocols. Collectors handle HTTP requests and normalization without CSV access. The repository owns persistence, locks, deduplication, and revisions. The service independently matches each metric to sources and evaluates freshness. The pipeline collects sources sequentially, isolates source failures, refreshes summaries, and validates prediction, risk, and recommendation outputs. The frontend and agent consume structured data through HTTP or the shared reader.

pipeline.refresh continues after individual source failures. Repository disk-write failures still propagate rather than being reported as successful ingestion. route_environment_latest is a cached materialized view; get_route_environment recalculates state at the requested time. pipeline.run projects rainfall into the existing Conditions contract to preserve the original prediction and recommendation interfaces while exposing complete environment and risks outputs.

## Matching Extension

StartPointStrategy uses the first original GeoJSON coordinate as the route representative point. Each station metric independently selects the nearest station with usable observations for that metric, preferring fresh stations. A source beyond 15 km produces missing. If no fresh source is available, the nearest stale source is selected and labelled stale.

WBGT and heat stress do not assume that temperature stations supply those metrics. Regional sources follow the curated TOML assignments. Station distance is a straight-line spherical distance, not a travel distance.

Future along-route sampling can be introduced through geometry_strategy and an extended segment-level matching and aggregation strategy. The current implementation does not claim along-route precision.

## PostgreSQL Migration

Implement EnvironmentRepository with a PostgreSQLRepository and replace its construction in bootstrap. Preserve observation keys, revision history, as_of availability rules, source_kind isolation, concurrency guarantees, and typed return contracts.

Collectors, the service, the frontend, and agent consumers should not need CSV-path changes. Prediction snapshot storage remains a repository responsibility. The static route catalog can remain CSV/GeoJSON or move into database tables. This version has no production database driver or paid database dependency.

## Continuous Worker

pipeline/worker.py calls the same pipeline.refresh(due_only=True) path. The repository port owns the lifetime worker lease, persisted worker state, and database status report. Only live data mode is accepted. Source cooldowns survive restarts through ingestion_runs.csv. The web server does not automatically start a worker. Docker Compose defines a separate collector service sharing the existing runtime volume. See LIVE_COLLECTION.md for operation and limitations.

## Category Storage

The repository routes metrics into weather, air_quality, and heat_stress observation and revision tables while keeping the existing environment_snapshot and get_route_environment interfaces. locations remains shared and source-specific. Category tables are long-format observations, not synchronized wide rows. CSV encoding converts time columns to Asia/Singapore local seconds without suffixes and restores aware datetimes on read. No collector or prediction module needs to interpret CSV timestamps directly.
