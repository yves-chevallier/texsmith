# Phase 01 — Baseline & Safety Net

## Goals
- Capture current behavior around templates, fragments, attributes, slots, partials, and assets.
- Establish regression tests to guard precedence/order and discovery before refactors start.

## Tasks
- Inventory built-in templates/fragments/partials; map owners/emitters/consumers and slot targets.
- Snapshot current CLI output for `texsmith --template-info` (article/book/letter/snippet) for later diffing.
- Add regression tests:
  - Attribute precedence: user > frontmatter (per file order) > fragments > template > core defaults.
  - Slot defaulting in template manifest (single default slot, fallback to `mainmatter`).
  - Fragment rendering order and slot/variable validation.
  - Template asset copying (templated and raw) including overrides.
- Note current partial precedence behavior in markdown pipeline.

## Tests / Acceptance
- New tests red/green on baseline, failing if behavior drifts.
- Fixtures recorded for current `--template-info` outputs.

## Deliverables
- Test cases + fixtures committed; no functional changes yet.
