# Partials & Override Precedence

TeXSmith renders LaTeX through reusable partials (Jinja templates) for list items, code blocks, images, etc. The override order is **explicit and enforced**:

1. **Template overrides** — declared under `latex.template.override` in `manifest.toml`. These always win.
2. **Fragment overrides** — declared via `partials` in `fragment.toml` or a fragment entrypoint. They apply after core defaults but are superseded by template overrides.
3. **Core defaults** — shipped with TeXSmith (`src/texsmith/adapters/latex/partials`).

Conflicts & requirements:
- Two fragments cannot override the same partial; TeXSmith raises a `TemplateError`.
- Templates and fragments can declare `required_partials` (list of names without extensions). Missing entries abort the render with a clear error.
- Providers are tracked so diagnostics can point to the template or fragment responsible.

Usage:
- Templates: list override paths in `manifest.toml` under `latex.template.override` (relative to the template root, `template/overrides`, or `overrides/`).
- Fragments: add `partials = ["strong.tex", "codeblock.tex"]` (or a `{ name = "path" }` mapping) plus optional `required_partials` inside `fragment.toml`. Entry points may return the same fields on the `Fragment` object.

Guidance:
- Prefer template overrides for document-wide styling or publisher branding.
- Use fragment overrides to co-locate rendering tweaks with the feature they own (callouts, code, glossary).
- Keep a single source of truth per partial; if a fragment needs to opt out, expose a fragment attribute instead of overlapping overrides. 
