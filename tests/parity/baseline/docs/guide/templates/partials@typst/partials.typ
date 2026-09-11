#set document(
  title: "Partials & Override Precedence",
)
#set page(
  paper: "a4",
  margin: 2.5cm,
  numbering: none,
  footer: context {
    if counter(page).final().first() > 1 {
      align(center)[#counter(page).get().first()]
    }
  },
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
  #text(size: 1.8em, weight: "bold")[Partials & Override Precedence]
]
#v(1.5em)

TeXSmith renders LaTeX through reusable partials (Jinja templates) for list items, code blocks, images, etc. The override order is *explicit and enforced*:

+ *Template overrides* — declared under `latex.template.override` in `manifest.toml`. These always win.
+ *Fragment overrides* — declared via `partials` in `fragment.toml` or a fragment entrypoint. They apply after core defaults but are superseded by template overrides.
+ *Core defaults* — shipped with TeXSmith (`src/texsmith/adapters/latex/partials`).

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
