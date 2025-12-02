# Phase 04 — Fragment System Revamp

## Goals
- Make fragments self-describing via manifest and a typed ABC, removing legacy `__init__.py` registration.
- Support fragment-level attributes/partials cleanly.

## Tasks
- Define fragment manifest schema (name, description, files/pieces with slot/kind/output, attributes, injection points/partials).
- Introduce `Fragment` ABC (dataclass-style) encapsulating metadata + render logic; keep shim for `create_fragment` with deprecation.
- Update registry to load fragments from manifest by default; keep compatibility path for entrypoint factory.
- Migrate built-in fragments (geometry, typesetting, fonts, callouts, code, glossary, index, bibliography, todolist, extra) to new manifest/ABC.
- Ensure fragment attributes use new owner/emitter rules; support fragment partial overrides.
- Remove legacy central `__init__.py` wiring once migrated.

## Tests / Acceptance
- Registry discovers built-ins via manifest; default order unchanged.
- Fragment slot/variable validation enforced; conflicts surface clearly.
- Fragment attributes resolve with overrides; partial overrides applied in pipeline.
- Backward-compat tests for old entrypoint still pass with deprecation notice.
