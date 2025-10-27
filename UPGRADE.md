# Upgrade Notes (2025.04 Architecture Refresh)

## Breaking changes

- The legacy `texsmith.domain.*` modules have been removed. Re-export shims remain in place under `texsmith.*`, but you should now target `texsmith.core.*` directly to avoid the extra layer.
- CLI entry points live under `texsmith.ui.cli`. Compatibility aliases keep `texsmith.cli.*` importable (including individual command modules), but update documentation and custom tooling to use the new namespace.
- Procedural helpers from `texsmith.api.pipeline` and `texsmith.api.service` have been consolidated. Prefer the new `ConversionService` interface instead of calling `split_document_inputs`, `prepare_documents`, or `execute_conversion` directly.

## New APIs

- `texsmith.api.service.ConversionService` with companion dataclasses `ConversionRequest` and `ConversionResponse`.
- `texsmith.core.conversion.TemplateRenderer` that centralises slot aggregation, bibliography emission, and LaTeX assembly.
- `texsmith.core.conversion.slots.DocumentSlots` providing a unified slot data model for CLI, templates, and programmatic users.
- `texsmith.core.diagnostics.DiagnosticEmitter` protocol with `NullEmitter` and `CliEmitter` implementations.

## Migration suggestions

1. Update library imports to rely on `texsmith.core` (contexts, conversion helpers, rules, templates) and `texsmith.api` for public orchestrators.
2. Replace any direct use of `texsmith.api.pipeline` helpers with `ConversionService`. Start by building a `ConversionRequest`, then call `prepare_documents()` followed by `execute()`.
3. When manipulating template slots, use the new `DocumentSlots` abstraction. Legacy attributes such as `Document.slot_overrides` have been removed.
4. If you previously relied on `ConversionCallbacks`, pass an emitter object instead. The CLI exposes `CliEmitter` for convenience; you can subclass `DiagnosticEmitter` for custom behaviour.
5. Regenerate documentation snippets or scripts that referenced `texsmith.cli.commands.*` modules so they point to `texsmith.ui.cli.commands.*` (the compatibility layer remains for this release but will be dropped in a future major bump).

## Release checklist

- [x] Pyright
- [x] Ruff
- [x] Pytest (full suite)
- [x] README / docs updated with new architecture, ConversionService examples, and diagnostics guidance.
- [x] End-to-end conversion verified (`texsmith convert examples/markdown/features.md --output build/e2e-output`).
- [x] Compatibility aliases registered for `texsmith.cli.commands.*` to keep existing tooling working.
