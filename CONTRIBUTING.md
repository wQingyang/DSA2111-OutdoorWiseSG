# Contribution policy

Read docs/TEAM_HANDOFF.md and docs/CSV_SCHEMA.md before edits. Own one module directory; contracts and bootstrap changes require integration owner review. Do not read/write CSV outside repository or request environment APIs from model/agent/frontend modules. Preserve route IDs and null/status/provenance semantics. Run `python -m pytest -q`. New endpoint collectors must include official recorded payload fixtures; mock-only tests are not evidence of real API integration.
