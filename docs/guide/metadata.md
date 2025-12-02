# Metadata Conventions

TeXSmith normalises a handful of common front matter fields so that templates and
fragments can rely on a single canonical name. External configuration files, CLI
`--attribute` overrides, and Markdown `press.*` blocks are all merged before the
template resolver runs, so manifests only need to reference the final attribute
name (for example `emoji`, `glossary_style`, or `width`). The preprocessing
stage keeps the full `press` tree available for backwards compatibility, but the
rest of the codebase no longer needs to reference dotted `press.*` paths.

## Authors

Author metadata is validated with Pydantic and converted into a list of objects
with `name` and `affiliation` keys. TeXSmith accepts a few flexible input
shapes, but always prefers the `authors` key in the front matter. The following
examples are all valid and will be converted into the canonical structure:

```yaml
---
authors: "Ada Lovelace"
---
```

```yaml
---
authors:
  - "Ada Lovelace"
  - "Grace Hopper"
---
```

```yaml
---
authors:
  - name: Ada Lovelace
    affiliation: Analytical Engine
  - name: Grace Hopper
    affiliation: US Navy
---
```

```yaml
---
authors:
  name: Ada Lovelace
  affiliation: Analytical Engine
---
```

Each entry is trimmed, validated, and stored as `{ "name": ..., "affiliation": ... }`.
If any entry is missing a name, TeXSmith raises an error before the template
render begins.

Although the front matter parser still understands the legacy `author` key, you
should prefer the plural `authors` form so that your metadata mirrors the
canonical shape.

## Other Common Fields

The same copying behaviour applies to the other common fields. If your document
only declares:

```yaml
---
title: Sample Report
subtitle: Q2 Findings
date: 2024-07-01
---
```

the resulting template context exposes `press.title`, `press.subtitle`, and
`press.date`. Templates no longer look at the root-level keys, so you can always
depend on the `press` namespace inside templates and fragments.

## Attribute ownership & consumers

- **Owner**: each attribute belongs to either the template (default) or a fragment (`fragment.toml` attributes set `owner = <fragment name>` implicitly). Conflicting owners raise a `TemplateError`.
- **Emitter**: templates can surface derived attributes through `emit` in `manifest.toml` so renderers see both declared attributes and emitted helpers (for example, `callout_style` or `code.engine`).
- **Consumer**: any template/fragment/renderer code that reads the attribute. Consumers should only read attributes they own or that are explicitly emitted.
- Precedence: CLI/front matter overrides → attribute resolver (type coercion, normaliser, escape) → emitted defaults → render-time context.

When adding new attributes, pick a single owner (template or fragment) and document the sources that are allowed to override it. 
