# Arguments

## Attribute ownership & consumers

- **Owner**: each attribute belongs to either the template (default) or a fragment (`fragment.toml` attributes set `owner = <fragment name>` implicitly). Conflicting owners raise a `TemplateError`.
- **Emitter**: templates can surface derived attributes through `emit` in `manifest.toml` so renderers see both declared attributes and emitted helpers (for example, `callout_style` or `code.engine`).
- **Consumer**: any template/fragment/renderer code that reads the attribute. Consumers should only read attributes they own or that are explicitly emitted.
- Precedence: CLI/front matter overrides → attribute resolver (type coercion, normaliser, escape) → emitted defaults → render-time context.

When adding new attributes, pick a single owner (template or fragment) and document the sources that are allowed to override it.
