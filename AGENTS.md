# OutdoorWise maintenance instructions

OutdoorWise is a working FastAPI application with a vanilla JavaScript frontend.
Inspect the current checkout, `git status`, README and relevant contracts before editing.
Preserve existing local changes; do not treat Git HEAD or historical reports as the implementation.

## Architecture

- `api/app.py` composes the HTTP application; `bootstrap.py` composes the environmental pipeline.
- `collectors/` handles external transport and normalization; `pipeline/` owns collection orchestration and worker scheduling.
- `storage/` owns operational environmental CSV access; `services/` performs catalog matching and supplementary live estimates.
- `contracts/` defines units, timestamps and typed boundaries; `modules/` implements risk, eligibility and shared ranking.
- `accounts/`, `personalization/`, `difficulty/` and `export/` provide identity, user adaptation, effort estimates and GPX.
- `llm/` interprets Tab 2 preferences through OpenRouter; `routing/` validates ORS geometry and current-environment assessments.
- `prediction/` is protected offline research and historical inference. API adapters handle application compatibility.
- `analysis/station_matching/` is independent spatial-method evidence, never an application startup dependency.
- `frontend/`, `tests/` and `deploy/` contain presentation, regression checks and deployment preparation.

## Preserve behavior and evidence

- Keep application mode (`live`/`historical`) independent of repository data mode (`live`/synthetic `demo`).
- Live uses available current observations and Now only. Never replace missing live inputs with historical or synthetic data.
- Historical replay uses the fixed snapshot/reference. Distinguish departure risk from full-run coverage; preserve delayed unknown-risk fallback and evaluation-only ground truth.
- Tab 2 remains the current-environment workflow in both application modes. LLMs interpret preferences; deterministic code owns geometry, feasibility, risk and ordering.
- Do not alter risk formulas, thresholds, route counts, prediction mathematics, preprocessing, horizons, coefficients, datasets or saved evaluations without an explicit request.
- Missing, stale, unavailable and actual zero are distinct. Preserve station/region matching, provenance, availability timestamps and revision history.
- CSV schema v3 timestamps are Singapore-local `YYYY-MM-DDTHH:MM:SS` without a suffix. Never parse them as UTC. Use the repository for operational environmental persistence.
- API requests consume snapshots; the existing collector owns scheduled collection. Do not add per-route external weather calls or request-time model training.
- Shared feasibility/risk filtering precedes personalization. Personalization only reorders survivors by difficulty mismatch with original shared rank as tie-breaker; it cannot restore excluded routes or overwrite shared scores.
- Account/session SQLite and per-user personalization JSON are separate stores. Derive identity from authenticated context; preserve isolation, scrypt hashing, HttpOnly sessions and feedback linkage. Never log credentials/tokens or save simulations as completed runs.
- Profiles remain derived from eligible history; prevent future/current-run feedback leakage. Difficulty is an effort estimate, not medical advice. GPX retains GeoJSON longitude/latitude order correctly.
- Protect `data/runtime/`, catalog geometry, frozen datasets and research evidence. Use temporary test storage. Do not delete ignored runtime files or migrate storage during maintenance.
- Keep one API worker/replica and one collector until a shared durable-storage design supports scaling. Do not deploy, allocate cloud resources, commit or push unless requested.

## Validation and documentation

Use English for source comments, UI and documentation. Explain non-obvious assumptions and failure behavior; keep one authoritative document per subject. Update references when moving files.

Run focused checks, then `.venv/bin/python -m pytest -q`, `npm test`, `npm run test:browser`, `docker compose config --quiet`, `kubectl kustomize deploy/k8s`, and `git diff --check` when relevant. Keep scientific/data checksums unchanged during cleanup. Distinguish mocked provider tests and manifest rendering from real provider access or deployment success. Report changed paths, actual test results, data/security implications and remaining limitations.
