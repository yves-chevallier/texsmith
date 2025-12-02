# Phase 08 — Cleanup & Deprecations

## Goals
- Remove legacy code/attrs/assets and land deprecations cleanly after migrations.

## Tasks
- Delete cover assets and removed attributes (logo/cover/covercolor, columns, backmatter/emoji/preamble as decided).
- Remove legacy fragment `__init__.py` registration code once ABC/manifest adoption is complete; keep minimal shims with clear deprecation messaging until then.
- Drop deprecated attribute paths/aliases after warning period; update tests accordingly.
- Final sweep for duplicate attribute definitions (SSOT) and stray latexmkrc in templates.

## Tests / Acceptance
- Test suite passes without deprecated paths; deprecation warnings removed or flagged as intentional.
- No stray assets/attributes remain; template info reflects final state.
