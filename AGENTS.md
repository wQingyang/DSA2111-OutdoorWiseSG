# OutdoorWiseSG — Codex Repository Instructions

## Mission and source of truth
OutdoorWiseSG is a DSA2111 group project for recommending Singapore running routes using geographic data, environmental observations, running preferences, and optional LLM assistance. The repository contains a working application, not just a proposed architecture. **Inspect existing code and tests before editing.** Documentation may describe intended functionality; distinguish it from tested implementation.

At the beginning of each task:
1. Check `git status`, current branch, and relevant recent commits. Do not silently discard local changes.
2. Read `README.md`, this file, and topic-specific documentation such as `docs/CSV_SCHEMA.md` and `docs/PERSONALIZATION.md`.
3. Trace the concrete route from API endpoint to service, repository, contracts, frontend, and tests.
4. Explain substantial proposed changes and identify team-owned modules affected.
5. Prefer the smallest compatible change over a broad rewrite.

## Architecture map
- `outdoorwise/api/app.py`: FastAPI application and router registration.
- `outdoorwise/collectors/`, `pipeline/`, `storage/`, `services/route_environment.py`, `contracts/`: environmental ingestion, contracts, persistence, route-level environmental assessment.
- `outdoorwise/modules/`: baseline prediction, risk, and recommendation logic.
- `outdoorwise/agent/`: existing agent/chat integration. Do not assume the LLM provider is configured.
- `outdoorwise/accounts/`: registration, login, sessions, and account identity.
- `outdoorwise/personalization/`: per-user running history, favourites, feedback, derived profiles, personalized difficulty, and ranking.
- `outdoorwise/difficulty/`: generic difficulty estimates.
- `outdoorwise/export/`: GPX route export.
- `outdoorwise/evaluation/`: personalization evaluation and synthetic fixtures.
- `frontend/`: Leaflet map, user flows, account and profile pages, personalization UI.
- `config/`, `data/`, `docs/`, `tests/`: config, routes/runtime data, documentation, and regression tests.

## User identity and personalization — preserve these invariants
The current team implementation distinguishes **authenticated users**; do not treat profiles as a single shared global user.
- Registration/login/logout and username availability are implemented. Usernames are case-insensitively unique; user IDs are immutable UUIDs.
- Passwords use scrypt hashing; sessions are server-side and exposed through an HttpOnly cookie. Never store plaintext passwords, log session tokens, or expose password hashes.
- The accounts repository uses **SQLite** for account/session records. This is a deliberate exception to CSV-first environmental persistence; do not replace or migrate it without approval.
- The personalization repository currently persists completed runs, favourites, and feedback as atomic **JSON** files under `data/runtime/personalization/`, scoped via `user_id`. Do not inaccurately describe these as CSV or SQLite.
- All user-specific reads and mutations must derive identity from authenticated server-side context, not a client-supplied arbitrary `user_id`. Preserve per-user isolation, including lookup/update/delete operations and links between feedback and a completed run.
- The derived running profile summarizes distances, pace, comfortable distance, difficulty feedback and confidence. It is computed from the user's history; do not introduce a competing authoritative stored profile without explicit design approval.
- Generic difficulty is a 1–5 **effort estimate**, not medical advice. Its heat fallback order is WBGT, then official heat-stress category, then temperature/humidity; avoid double counting.
- Personalized difficulty calibrates generic predictions using only eligible past runs/feedback, with cold-start handling. Never leak future/current-run feedback into the prediction for that run.
- The original team recommender defines the feasible candidate set and environmental filtering. Personalization **only reorders those candidates** by target-difficulty mismatch, with original rank as tie-breaker. Never reintroduce an excluded route or silently overwrite the underlying score. Favourites currently do not affect this ranking.
- Keep authenticated and unauthenticated frontend flows functional: the public/generic recommendation route remains available; authenticated users may receive personalized ranking and history.
- Keep GPX export compatible with existing route GeoJSON ordering and correct latitude/longitude coordinate conventions.

## Environmental pipeline and data contracts
- Environmental observations are CSV-first, not an excuse to migrate all project storage to a single database. The **current canonical storage schema is version 3** in `docs/CSV_SCHEMA.md`. Use the implementation/contracts and that document, not earlier design proposals.
- Current categories: `weather_observations.csv` / `weather_observation_versions.csv`; `air_quality_observations.csv` / `air_quality_observation_versions.csv`; `heat_stress_observations.csv` / `heat_stress_observation_versions.csv`; plus unified `locations.csv` and additional documented runtime metadata.
- CSV timestamps are Singapore-local `YYYY-MM-DDTHH:MM:SS`, second precision, **without** a timezone suffix. Parse external times with explicit timezone handling and never interpret stored offset-free CSV times as UTC.
- Preserve revision/history semantics, metric units, missing-value distinctions, station-vs-region identities, ingestion provenance, and non-destructive failure behavior.
- Live API failures must not be silently replaced with demo/synthetic measurements or advertised as real observations.
- Poll source APIs according to published update frequency/configuration; implement bounded retries and timeouts. Route-level risk estimates must disclose missing, stale, simulated, or spatially coarse measurements.
- Keep route geometry reusable/offline for recommendation requests. Avoid making latency-sensitive user requests dependent on fresh OSM/Overpass route generation. Treat route catalogs as changeable and inspect current `data/` rather than assuming only two routes exist.

## LLM and service boundaries
- Deterministic code should handle geometry, feasibility filtering, risk metrics, and ranking. An LLM may interpret language, orchestrate approved tools, or explain the recommendation, but must not invent weather readings, route geometry, user history, or tool outcomes.
- Keep ingestion, environmental evaluation, recommendation, authentication, and UI responsibilities separated via existing APIs/contracts.
- Preserve future container/Kubernetes deployability, but do not prematurely split the application into paid infrastructure services. Account SQLite and personalization JSON files require an explicit durable/shared-storage plan before scaling to multiple writers or replicas.
- Never hardcode tokens, API keys, credentials, or private user data. Avoid committing local runtime databases, history, cookies, or generated secrets.

## Team boundaries and change discipline
The current developer primarily works on data ingestion, CSV persistence, route geometry, and pipeline integration; account, personalization, difficulty, ranking and frontend code include teammates' work. They may be changed when necessary, but changes must be narrow, explained, and regression-tested. Avoid deleting teammates' features, changing shared API response shapes without coordination, or mixing unrelated refactors into one task.

- All repository docs, code comments, tests, UI copy and commit messages must be in English.
- Do not reintroduce deprecated CSV schemas or migration paths unless explicitly requested.
- Do not claim a feature, accuracy number, passing test count or deployment status without verifying it in this checkout.
- Before altering storage schemas, auth flows, ranking semantics or public endpoints, document compatibility and migration implications.
- Do not commit, push, force-push, merge to `main`, or open a PR without explicit instruction. Never rewrite shared Git history.

## Validation expectations
- Run focused tests for modified modules, then `python -m pytest -q` when feasible.
- For authentication/personalization changes, include multiple users and verify isolation, missing/invalid sessions, cold start, feedback linkage, no future leakage, and generic fallbacks.
- For data changes, test timestamp round-trips, revision/deduplication, API failures, source labeling and compatibility with route/environment endpoints.
- For frontend/API changes, verify account flows and recommendation/profile displays. Report any tests not run; do not imply success from README statements alone.
- Never exercise tests against real users' production data. Prefer temporary directories and fixtures.

## Durable project memory and completion report
If `docs/PROJECT_CONTEXT.md` and `docs/DEVELOPMENT_STATUS.md` exist, read them, but defer to the current implementation on factual conflicts. If a status file is missing, propose initializing it based on actual inspection rather than inventing progress. Update it when meaningful architecture or functionality changes and document only verified progress.

At task completion, report: (1) what changed and why, (2) file paths, (3) tests run and results, (4) any user-data/security implications, (5) outstanding limitations and next steps. Ask before carrying out a destructive or costly operation.
