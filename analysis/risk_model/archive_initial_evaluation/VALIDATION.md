# Validation record

Validated against this checkout on October 30, 2026 (Singapore time).

- `analyze.py`: completed; 661 controlled sensitivity samples and 75/75 explicit
  eligibility/boundary cases passed. These are rule conformance counts, not accuracy.
- `.venv/bin/python -m pytest -q analysis/risk_model`: 4 passed, including independent
  hand calculation, input-branch behavior, production/adapter availability equivalence,
  deterministic ranking ties and consistent unknown/block handling across baselines.
- `.venv/bin/python -m pytest -q analysis`: 17 passed, including existing freshness tests.
- `.venv/bin/python -m pytest -q`: 176 passed in 105.15 seconds; one existing
  Starlette/httpx deprecation warning. The default testpaths cover `tests/`, so
  the analysis tests were explicitly run separately.
- Independent rerun using `--output-dir /tmp/outdoorwise-risk-reproduction`:
  all 11 generated artifacts were byte-identical (six CSVs, four figures,
  `verification.json`).
- All 124 protected application/configuration/data SHA-256 entries remained
  unchanged after the experiments and test runs. Source hashes are in
  `verification.json`; no application or source data edits appear in Git status.
- Figure 1 PNG: 2148×1410 pixels; Figure 2: 2148×1950 pixels, both 300 DPI.
  Both PDFs contain embedded TrueType font streams and no raster image objects.
  All displayed text passed canvas-bound checks. Both PNGs were visually inspected
  for legibility, overlap, clipping and meaningful axes.
- `git diff --check`: passed.

External environmental endpoints, collectors, training and deployment were not
started. Application regression tests use local fixtures and mocked providers;
their success is not real-provider validation. Frontend/browser and deployment
checks were not relevant to these isolated Python/report additions and were not run.
No commit or push was performed.
