# Validation record

Validated against this checkout on October 30, 2026 (Singapore time).

- `analyze.py`: completed; 661 controlled sensitivity samples and 75/75 explicit
  eligibility/boundary cases passed. These are rule conformance counts, not accuracy.
- `.venv/bin/python -m pytest -q analysis tests/test_collector_reliability.py`:
  **34 passed**. Includes independent hand calculation, 10 PM2.5 unusability/fallback
  cases, nonzero PM2.5 precedence, every sweep's component sum, production/adapter
  version equivalence, existing freshness checks, native wrapper/worker fixtures,
  source recovery, killed-worker restart, lease release and unknown API disclosure.
  Archived test source is excluded from collection; the active expanded tests run.
- `.venv/bin/python -m pytest -q`: **181 passed** in 71.65 seconds; one existing
  Starlette/httpx deprecation warning. The default testpaths cover `tests/`, so
  the analysis tests were explicitly run separately.
- `npm test`: **29 passed**, including unknown/stale/future disclosure and explicit blocks.
- `npm run test:browser`: passed mocked-provider browser and actual local FastAPI
  desktop/mobile live/historical checks, with isolated temporary storage.
- Independent rerun using `--output-dir /tmp/outdoorwise-risk-reliability-reproduction`:
  all **19 generated artifacts** were byte-identical (14 CSVs, four figures,
  `verification.json`).
- `--plots-only` reproduces the figures directly from saved CSV coordinates.
- All **64 pre-existing data/research/configuration/scoring files** in the initial
  audit manifest remained byte-identical. All **17 original evaluation artifacts**
  remain byte-identical in `archive_initial_evaluation/`. Original numerical columns
  in the five scientific result tables are asserted unchanged during every run.
  New `verification.json` hashes record current code/inputs; collector observability
  edits are intentional and do not affect the risk model or CSV schema.
- Figure 1 PNG: 2148×1410 pixels; Figure 2: 2148×1050 pixels, both 300 DPI.
  Both PDFs contain embedded TrueType font streams and no raster image objects.
  All displayed text passed canvas-bound checks. Both PNGs were visually inspected
  for legibility, overlap, clipping and meaningful axes.
- `git diff --check`: passed.
- `docker compose config --quiet` and `kubectl kustomize deploy/k8s`: passed;
  manifests were rendered only. No deployment or real-provider validation occurred.
- Rendered LaunchAgent plist passes native `plutil -lint`; the wrapper passes
  `/bin/zsh -n`. Rendering did not install or start a persistent service.

External environmental endpoints, real collection, training and deployment were not
started. Worker subprocess tests use temporary storage, recorded payloads/mocks and
seeded cooldowns so no live requests occur. Killed-worker restart and SIGTERM/SIGHUP
shutdown were exercised; the native launchd restart engine, sleep/wake, logout/login
and reboot were not activated/tested. No sleep/privacy settings changed. No commit
or push was performed.

## Changed paths and scope

- `analysis/risk_model/analyze.py`, `test_evaluation.py`: refined figures, saved-CSV
  plotting, original numerical checkpoints and expanded PSI/aggregate verification.
- `analysis/risk_model/reliability_audit.py`: read-only source/run/coverage audit.
- Analysis CSVs: original six retained/reproduced, with additional ranking-summary
  columns; eight new provenance/coverage/ranking-effect/polling evidence tables.
- Both PNG/PDF pairs regenerated; original versions preserved in the archive.
- `analysis/risk_model/README.md`, `RESULTS.md`, `COLLECTOR_AUDIT.md`,
  `report_sections.tex`, `VALIDATION.md`, `verification.json`: updated methods,
  evidence, concise report material and validation. Archive contains all original
  files plus a collection exclusion for archived test source.
- `outdoorwise/cli.py`, `pipeline/worker.py`: additive lifecycle diagnostics and
  catchable stop-signal reporting, including SIGHUP.
- `outdoorwise/pipeline/runner.py`: additive batch-fetch timestamp in JSON reports;
  scheduling, transport, ingestion decisions and recommendation logic unchanged.
- `outdoorwise/storage/repository.py`: additive status fields derived from existing
  logs/records; `contracts/ports.py`: bounded error-category helper. No CSV migration.
- `scripts/render_macos_collector.py`, `scripts/run_macos_collector.zsh`: inert plist
  renderer and foreground wrapper for explicit operator installation.
- `tests/test_collector_reliability.py`: temporary-storage recovery/diagnostic/API tests.
- `README.md`, `docs/LIVE_COLLECTION.md`, `docs/LOCAL_COLLECTOR_MACOS.md`: operating
  instructions and limits. The existing local `analysis/README.md` index edit is retained.

No scoring/policy/ranking module, source collector/parser, production configuration,
CSV dataset, research artifact, frontend or deployment manifest changed.
