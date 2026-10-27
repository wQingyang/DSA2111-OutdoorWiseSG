# Repository cleanup audit — 27 October 2026

## Scope and baseline

This is maintenance of the implemented system, not feature development. The checkout
was on `main` at `d513ece`, with extensive existing tracked/untracked integration
changes. Those changes were preserved; Git HEAD was not treated as current code.
Baseline inventories/hashes and Git status are under `/tmp/outdoorwise-cleanup-audit/`.
No commit, push, staging/index rewrite or deployment was performed.

Before edits: **176 Python tests**, **29 frontend tests**, synthetic and actual-backend
Chromium suites, Compose validation and Kubernetes manifest rendering passed. The
baseline inventory excluded dependencies, caches, secrets and Git internals. All 81
production Python modules were parsed for import inspection; configured/dynamic entry
points were checked separately rather than inferring liveness from direct imports alone.

## Dependency audit and decisions

- **Active production:** `api.app:create_app`, `bootstrap.build_pipeline`, `cli.main`,
  registered FastAPI routers/dependency overrides, the source registry, persistence,
  risk/ranking, account/user services, LLM parsing/explanation, ORS and exports.
- **Frontend:** index/login/register/profile script and stylesheet references were
  traced; shared rendering/location/difficulty/personalization/export remain active.
  No producer references the old `forecast-ranked-*` or `unified-route-card` classes.
- **Protected research:** historical API dynamically imports prediction siblings via
  its explicit compatibility boundary. Training scripts are valid offline deliverables,
  not dead modules. All seven research entry modules and the frozen evaluator imported
  successfully without invoking training or rewriting evidence.
- **Independent experiment:** both mapping scripts are used by the saved study/analysis
  and test imports. Only their root/default/reproduction paths and two unused path
  constants changed. Mathematical/control-flow ASTs match after those path substitutions.
- **Compatibility:** original observation/personalized APIs, native replay, legacy
  experimental ranking, supplementary live persistence and optional LLM explanations
  remain. Tests and client/research contracts justify retention. The unavailable-risk
  fallback and typed ports are retained rather than deleting valid explicit disable paths.
- **Deletion evidence:** templates contain only unbound NotImplementedError placeholders;
  package discovery includes only outdoorwise, and no runtime, test, CLI, Docker or
  Kubernetes path loads them. References existed only in obsolete contribution/handoff
  notes. The old agent directory contained bytecode only, with no source or registered
  router. The old partial requirements snapshot was unused by installation/CI/Docker
  and omitted the current scientific/LLM dependencies. Current dependencies remain in
  pyproject.toml and the frontend lockfile.
- **Documentation:** technical source/CSV/risk/personalization/location/deployment
  references remain. Current tests and historical integration findings have one home.
  Dated real collection JSON/response evidence is archived with its scope. Scientific
  mapping CSVs, figures, analysis and findings are retained under a subject-based path;
  old demo/work logs are explicitly historical, not operating instructions.
- **Generated local artifacts:** virtual environments, Node dependencies, bytecode,
  pytest/egg caches and Finder metadata are not production modules. Ignore rules remain.
  Only the orphan agent cache and already-empty screenshot directories were removed;
  dependencies and operational runtime files were not purged.

## File operations

The table is scoped to this cleanup, not every pre-existing Git diff. Directory moves
include their existing contents. Deleted checkpoint documents were consolidated only
after current contracts, behavior and remaining limitations were retained elsewhere.

| Original file | Action | New location | Reason |
|---|---|---|---|
| `scripts/compare_route_mapping.py` | Moved | `experiments/station_route_matching/scripts/compare_route_mapping.py` | Independent offline spatial matching experiment; no startup dependency |
| `scripts/analyze_route_mapping.py` | Moved | `experiments/station_route_matching/scripts/analyze_route_mapping.py` | Analysis and plotting for saved experiment CSVs |
| `docs/haoyun/mapping-results` | Moved | `experiments/station_route_matching/results` | Preserve all saved CSV results and analysis |
| `docs/haoyun/figures` | Moved | `experiments/station_route_matching/figures` | Preserve research figures and recorded demo screenshots |
| `docs/haoyun/mapping-study.md` | Moved | `experiments/station_route_matching/results/study.md` | Preserve methodological findings under subject-based organization |
| `docs/haoyun/work-log.md` | Moved | `experiments/station_route_matching/archive/work-log.md` | Historical experimental provenance, not current application instructions |
| `docs/haoyun/demo-script.md` | Moved | `experiments/station_route_matching/archive/demo-script.md` | Historical demo evidence; obsolete controls explicitly labeled |
| `docs/verification.json` | Moved | `docs/evidence/collection/verification.json` | Dated collection/source evidence; not a current API contract |
| `docs/collection_verification.json` | Moved | `docs/evidence/collection/collection_verification.json` | Dated collection/source evidence; not a current API contract |
| `docs/continuous_collection_verification.json` | Moved | `docs/evidence/collection/continuous_collection_verification.json` | Dated collection/source evidence; not a current API contract |
| `docs/example_run.json` | Moved | `docs/evidence/collection/example_run.json` | Dated collection/source evidence; not a current API contract |
| `docs/VERIFICATION.md` | Moved | `docs/evidence/collection/README.md` | Keep dated live collection evidence separate from current verification |
| `templates/module_template.py` | Deleted | — | Unbound placeholder classes; no runtime/test/packaging/deployment imports |
| `CONTRIBUTING.md` | Deleted | — | Obsolete six-person ownership workflow; maintenance constraints consolidated in AGENTS.md |
| `docs/TEAM_HANDOFF.md` | Deleted | — | Superseded ownership/templates/legacy-agent instructions |
| `docs/DEVELOPMENT_STATUS.md` | Deleted | — | Superseded checkpoint chronology; current verified behavior retained in FINAL_INTEGRATION.md |
| `docs/FRONTEND_VERIFICATION.md` | Deleted | — | Current test commands and coverage consolidated into FINAL_INTEGRATION.md |
| `frontend/forecast-ranking.css` | Deleted | — | All selectors belong to removed forecast dashboard; no active class producer |
| `outdoorwise/agent/` | Deleted | — | Cache-only orphan; no source modules or imports remain |
| `requirements.lock.txt` | Deleted | — | Unreferenced partial environment snapshot omits current scientific/LLM dependencies; pyproject.toml remains the supported installer |
| `docs/FINAL_INTEGRATION.md`, `docs/FRONTEND_VERIFICATION.md`, `docs/DEVELOPMENT_STATUS.md` | Consolidated | `docs/FINAL_INTEGRATION.md` | Keep current supported behavior, diagnostic matrix and verified tests; remove duplicated checkpoints and obsolete counts |
| `AGENTS.md` | Modified | Same path | Final architecture and safety constraints replace ownership/handoff procedures |
| `README.md`, `docs/ARCHITECTURE.md` | Modified | Same paths | One startup guide and explicit module/request-flow map |
| `docs/API_CONFIG.md`, `docs/LIVE_COLLECTION.md`, `docs/STARTING_LOCATION.md`, `docs/PERSONALIZATION.md`, `docs/ENVIRONMENTAL_RISK.md` | Modified | Same paths | Correct stale runtime/endpoint/storage descriptions and preserve unique technical assumptions |
| `outdoorwise/api/app.py`, `bootstrap.py`, `cli.py`, `config.py` | Modified | Same package | Expand dense startup/composition/CLI statements; remove two unused app imports; add boundary docstrings |
| `outdoorwise/contracts/ports.py`, `pipeline/runner.py`, `services/route_environment.py`, `storage/repository.py`, `llm/router.py` | Modified | Same package | Explain contracts, availability, matching, persistence and LLM authority without algorithm changes |
| `outdoorwise/api/forecast_ranking.py`, `api/time_selection.py`, `api/recommendation_workflow.py`, `modules/predictor.py`, `modules/recommender.py` | Modified | Same package | Replace prototype/owner comments with actual supported responsibilities |
| `outdoorwise/personalization/difficulty.py` | Modified | Same path | Remove unused comprehension over an empty list; document caller eligibility and input-order residual semantics; calibration mathematics unchanged |
| `frontend/index.html`, `frontend/style.css` | Modified | Same paths | Remove legacy stylesheet reference and selectors for obsolete card classes; active card/map/Tab 2 styles retained |
| `tests/test_route_mapping_experiment.py` | Modified | Same path | Import the relocated offline experiment; assertions remain intact |
| `tests/frontend_smoke.cjs`, `tests/frontend_backend_browser.cjs` | Modified | Same paths | Repair stale endpoint/rank-label assertions and execute that smoke check against an isolated browser-owned Live server |
| — | Added | `tests/conftest.py` | Isolate module-level default FastAPI storage before collection imports; restore environment and clean only its temporary directory afterward |
| `Dockerfile`, `deploy/README.md` | Modified | Same paths | Include existing saved evaluation JSON required by historical cards and correct stale documentation; deployment architecture unchanged |
| `prediction/`, `data/`, `docs/PREDICTION_MODELS.md`, `docs/forecast_evaluation.json` | Retained | Same paths | Protected model mathematics, artifacts, evidence, catalog and runtime data unchanged |
| `docs/contracts.schema.json`, `docs/csv.schema.json` | Retained | Same paths | Canonical typed/schema references; no schema regeneration or migration |
| Compatibility recommendation/time-selection/LLM explanation APIs | Retained | Existing API routers | Supported regression/client and research contracts; lack of frontend use is not deletion evidence |
| `outdoorwise/modules/risk.py:UnavailableRiskAssessor` | Retained | Same path | Explicit disabled-assessment fallback at the service boundary; not selected by normal bootstrap |
| `outdoorwise/evaluation/`, `scripts/evaluate_frozen_forecasts.py`, `scripts/copy_synthetic_fixture.py` | Retained | Same paths | Legitimate offline evaluation/fixture utilities with test or explicit command entry points |
| `.env.example`, `compose.yaml`, `deploy/k8s/`, `pyproject.toml`, `package.json`, `package-lock.json`, `.github/workflows/check.yml` | Retained | Same paths | Current environment, packaging, dependency, CI and deployment entry points |

## Final structure and responsibilities

The [complete source tree](REPOSITORY_TREE.txt) excludes dependencies, caches, Git
internals, local secrets and operating-system metadata. The main layout is:

```text
outdoorwise-main/
├── README.md, AGENTS.md, pyproject.toml, package.json, package-lock.json
├── Dockerfile, compose.yaml, .env.example
├── config/
├── outdoorwise/
│   ├── api/, bootstrap.py, cli.py, config.py
│   ├── collectors/, pipeline/, contracts/, storage/
│   ├── services/, modules/, routing/
│   ├── accounts/, personalization/, difficulty/, export/
│   ├── llm/, evaluation/
├── frontend/
├── prediction/
├── experiments/station_route_matching/
│   ├── README.md, scripts/, results/, figures/, archive/
├── data/catalog/, datasets/, runtime/
├── scripts/, tests/, docs/
└── deploy/README.md, k8s/
```

Collectors normalize official environmental payloads; the pipeline validates and
schedules ingestion; the repository preserves availability/revision history.
Catalog/dynamic matching supplies shared risk/eligibility and weighted ranking, then
personal difficulty reorders approved candidates. Historical research remains read-only,
with departure/coverage adapters outside prediction/. OpenRouter interprets Tab 2
preferences before deterministic ORS routing. The frontend presents structured results.
Docker/Kubernetes prepare one API and one collector over persistent local storage.
See [architecture](ARCHITECTURE.md) for exact modules and retained endpoints.

## Verification and preserved behavior

| Check | Final result |
|---|---|
| `.venv/bin/python -m pytest -q` | **176 passed**, one existing Starlette/httpx TestClient deprecation warning. |
| `npm test` | **29 passed**, zero failures. |
| `npm run test:browser` | Passed in Chromium: synthetic account/location flows and actual isolated Live/Historical FastAPI servers on desktop/mobile; Now/+30/+60, Tab 2 controls, map/GPX and repaired standalone HTTP smoke all pass. |
| `docker compose config --quiet` | Passed. |
| `kubectl kustomize deploy/k8s` | Passed manifest rendering; no cluster/API deployment performed. |
| `git diff --check` | Passed. |
| Relocated comparison and analysis | Passed: 1,317 sample rows, 288 summaries; analysis verified saved groups and rendered three temporary figures. |
| CLI/research entry checks | collect/status/run passed in isolated synthetic storage; research/evaluator imports passed without fitting or artifact regeneration. |
| Protected evidence | **80/80 SHA-256 checks unchanged**, including moved CSV/PNG/collection JSON at their new paths; no new source data files. |
| Reference checks | Local Markdown links, frontend assets and Docker COPY sources resolve. |


The relocated comparator ran against a temporary copy of environmental CSVs/catalog,
producing **1,317 sample rows and 288 summaries**. Analysis reproduced the saved live-retry
CSV grouping checks and three figures into `/tmp/outdoorwise-cleanup-matching`, without
overwriting any original result. The experiment's root imports and --help entry point
work; production startup does not depend on experiments/.

CLI collect/status/run passed using isolated synthetic storage and retained 12 routes.
No live official collection, external OpenRouter/ORS call, training, evaluation artifact
regeneration, Docker build/container start, Kubernetes API apply or cloud allocation was
performed. A font-cache warning during plotting did not prevent successful verification.

## Protection and unresolved limits

Before/after SHA-256 checks cover **80 files**: all baseline data/runtime/catalog/datasets
and prediction source/artifacts, frozen evaluation/model inventory, canonical schemas,
archived collection JSON, and relocated experimental CSV/PNG evidence. The manifest
maps old to new paths so a move cannot hide changed scientific output. Markdown changes
update links/organization and preserve findings. Baseline/current manifests are retained
outside the repo under `/tmp/outdoorwise-cleanup-audit/`; no account content or secret is
published in this report. Prediction/risk mathematics and recommendation behavior remain.

**Pre-existing tracking limitation:** Git already tracks an accounts database and some
runtime fixture/history files. Their bytes and index entries were deliberately not
changed. `.gitignore` prevents new untracked runtime artifacts from accidental addition
but does not untrack those existing paths. Docker excludes runtime contents. Before
public distribution, review provenance and make an explicit, separate index/history
sanitization decision; this cleanup neither publishes nor rewrites them.

Application limitations remain explicit in [FINAL_INTEGRATION.md](FINAL_INTEGRATION.md):
unknown delayed/full-run risk, provisional spatial/effort semantics, client-reported run
history, offline personalization-evaluation caveats and single-writer storage. Cleanup
does not repair scientific algorithms or change user-facing recommendation policy.

## Marking rubric mapping

1. **Code quality:** expanded dense composition/config/CLI code, removed dead imports,
   an unreachable placeholder and obsolete CSS/scaffolding; added isolated test startup.
2. **Structure and functionality:** clear runtime entry points, preserved compatibility
   contracts, subject-based experiment layout, and a single authoritative architecture
   and verification guide.
3. **AI/data analytics/deployment:** existing OpenRouter/ORS, ingestion/matching,
   observation and historical recommendation, protected prediction/evaluation research,
   Docker and Kubernetes are retained. The image now includes the existing saved
   evaluation JSON required by historical cards; no new AI or infrastructure is added.
4. **Source documentation:** concise explanations of availability, missing data,
   snapshot matching, deterministic versus LLM authority, ranking boundaries,
   startup composition and compatibility replace owner/template instructions.

## Work remaining for deployment

Build/run the image and Compose against a real Docker daemon; verify non-root volume
permissions, persistent data across restart and actual provider credentials/quotas.
Then load the image into an existing Kubernetes cluster, create secrets, validate API
objects, check PVC/locking behavior and probes, and record an actual rollout. Review
TLS/secure cookies and access controls before public hosting. These tasks are not run
or claimed successful by manifest rendering. Keep one API worker/replica and collector
until a separate shared-storage design supports more writers.
