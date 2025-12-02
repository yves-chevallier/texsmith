# Phase 02 — Attribute Model & Ownership

## Goals
- Clarify attribute ownership vs emission vs consumption, and enforce single-owner rule.
- Add template-level attribute emitters separate from declarations; keep permissive input with strict normalisation.

## Tasks
- Extend manifest schema to tag owner/emitter/consumer per attribute; enforce duplicate-owner error (template vs fragment).
- Add manifest key for template emitters (default values set at render/load time) without declaring ownership.
- Rework base-level handling:
  - Remove `article` base_level/backmatter and legacy preamble if unused.
  - Introduce `book` attribute `part: bool` to control slot depth (part vs chapter).
  - Keep base_level override plumbing only where necessary.
- Keep free-form user attributes allowed even without owners.
- Update runtime resolution to surface owner conflicts early.

## Tests / Acceptance
- Owner conflict raises clear error; emitter-only attributes allowed.
- Precedence still: user > frontmatter > fragments > template > core.
- `part` toggles slot depth as expected; article ignores backmatter/base_level.
- Attribute coercion/normalisation unchanged for valid inputs.
