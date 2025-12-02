# Fragments

Fragments are reusable LaTeX snippets injected into template slots. Built-in fragments (e.g., geometry, fonts, glossary, index) and custom ones share the same structure:

- `fragment.toml` with `name`, `description`, and either an `entrypoint` or a `files` list.
- Optional `attributes` section describing fragment-owned attributes (ownership enforced).
- Optional `partials` block for fragment-scoped partial overrides and `required_partials` for dependencies.
- Optional `should_render` logic (via entrypoint) to render only when needed.

## Manifest shape

```toml
name = "my-fragment"
description = "Short description."

[files.0]
path = "my-fragment.jinja.sty"  # or .tex
slot = "extra_packages"
type = "package"                # package | input | inline
output = "my-fragment"

[attributes.option]
default = true
type = "boolean"
sources = ["press.option", "option"]
description = "Controls feature X."
```

If you prefer Python logic, point `entrypoint` at a callable returning a `Fragment` or `FragmentDefinition`.

## Fragment pieces

- `package`: rendered to a `.sty` file and injected via `\usepackage` into the target slot.
- `input`: rendered to `.tex` and injected via `\input{}` into the target slot.
- `inline`: rendered string injected directly into the slot variable (no file emitted).

Slots are validated against the template at render time; inline injections must match declared slots or template variables.

## Attributes

Fragments can declare attributes (ownership enforced) and resolve overrides using the same `TemplateAttributeSpec` model as templates. Attribute defaults are injected into the context before rendering fragment pieces. Attribute ownership matters: if two fragments (or a template) claim the same attribute name, TeXSmith raises a `TemplateError`. Keep each attribute owned by a single fragment or the template to avoid conflicts.

## Partials

Fragments can ship their own partials so feature-specific rendering stays close to the feature:

```toml
partials = ["strong.tex", "codeblock.tex"]         # list form
required_partials = ["heading"]                    # fail fast if missing
```

or as a mapping when paths and names differ:

```toml
[partials]
codeinline = "overrides/inline/code.tex"
```

Partial precedence is template overrides > fragment overrides > core defaults. Duplicate fragment providers for the same partial abort the render.

## Runtime loading

- Built-ins are discovered under `src/texsmith/fragments/**/fragment.toml`.
- Custom fragments can be passed via `press.fragments` in front matter or CLI attributes.
- The registry uses manifest metadata first; entrypoint is a fallback.

## Migration notes for fragment authors

- Prefer `fragment.toml` with `files`, `attributes`, and optional `partials`/`required_partials` instead of legacy `__init__.py` registration.
- Entry points should return a `Fragment` or `FragmentDefinition`; `create_fragment()` remains compatible for now but is deprecated.
- Declare attribute ownership (implicit `owner = <fragment name>`) to avoid collisions with templates or other fragments.
- Keep slot targets aligned with template variables; inline targets must reference declared slots or template variables, otherwise a `TemplateError` is raised. 
