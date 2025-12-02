# Phase 05 — Partials & Markdown Integration

## Goals
- Make partial override precedence explicit and enforced across templates/fragments/core.
- Surface conflicts early and keep markdown conversion predictable.

## Tasks
- Define precedence: template overrides > fragment overrides > core defaults; document and enforce.
- Track which component supplies each partial; emit diagnostics on conflicts or missing partials required by fragments/templates.
- Ensure markdown engine initialises only after collecting all overrides; avoid implicit override order.
- Support fragment-provided partials via new manifest/ABC wiring.

## Tests / Acceptance
- Markdown → LaTeX uses expected partial when template and fragment both provide one.
- Conflict detection triggers for duplicate provider when not permitted.
- Precedence verified via targeted fixtures (e.g., emphasis/list/code rendering).
