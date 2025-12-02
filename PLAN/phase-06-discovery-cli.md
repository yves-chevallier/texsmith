# Phase 06 — Template Discovery & CLI Info

## Goals
- Make template discovery predictable across built-ins, pip packages, local trees, and user dirs.
- Improve `--template-info` output to surface slots/fragments/attributes clearly.

## Tasks
- Codify discovery order: built-ins, pip packages `texsmith-template-*`, cwd and parents, `~/.texsmith/templates`; consider caching.
- Implement CLI path: `texsmith --template=<name> --template-info` showing:
  - Slots (default flagged, depth/base info).
  - Fragments with descriptions and attributes.
  - Template attributes with Type/Format/Description columns.
- Update docs on discovery rules and `--template-info` usage.

## Tests / Acceptance
- Discovery tests for local + home + pip-style templates; deterministic ordering.
- CLI output fixtures updated (article/book/letter/snippet) with new columns.
- Friendly error for missing template or malformed manifest.
