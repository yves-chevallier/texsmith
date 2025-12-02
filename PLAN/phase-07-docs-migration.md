# Phase 07 — Documentation & Migration

## Goals
- Document the refactored concepts/pipeline and provide migration guidance.

## Tasks
- Write docs/guide entries for: Markdown extensions, templates, fragments, partials, attributes (owner/emitter/consumer), precedence, pipeline order.
- Add template discovery guide (built-ins, pip packages, cwd parents, user dir) and mermaid config per-template guidance.
- Update template docs for appendix slot, removal of cover/twocolumn/backmatter/emoji attributes, and new `book` `part` attribute.
- Create migration notes for fragment authors (new manifest schema, Fragment ABC) and template authors (emitter key, attribute removals, asset layout).
- Update README/CHANGELOG summaries.

## Tests / Acceptance
- Docs build cleanly; lint/link checks pass.
- Migration guide referenced from release notes.
