#set document(
title: "Templates",
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
#text(size: 1.8em, weight: "bold")[Templates]]
#v(1.5em)

#ts-callout-style.update("fancy")

TeXSmith templates define the #ts-logo("LaTeX") skeleton that wraps converted Markdown. Each
template bundles assets, slot definitions, attribute schemas, and build metadata
so you can aim the renderer at anything from articles to slide decks.

Templates are a core feature that allows TeXSmith to be extended for different
use cases. You may use:

- Custom project templates stored in a `templates/` folder.
- Local user templates installed in your `~/.texsmith/templates/` folder.
- Published templates installed from PyPI.
- Built-in templates included with TeXSmith.

= Built-in templates

TeXSmith includes standard templates for common document types:

- `article`: academic-style article layout with title page, abstract, and sections.
- `book`: book-style layout with parts, chapters, preface, table of contents, appendices, and optional `part` base-level override.
- `letter`: formal letters with sender/recipient metadata, fold marks, and signature.
- `snippet`: standalone `tikzpicture` frame for screenshots, stickers, and snippets.

Invoke them in the CLI with `-tarticle` or `-tletter`. Additional community templates remain available under `templates/` or as separate PyPI packages.

Take a look at built-in fragments for full configuration options.

= Quick start

```bash
# 1. Inspect a built-in template
texsmith --template article --template-info

# 2. Render a document with template slots + build
texsmith docs/intro.md \
  --template article \
  --slot mainmatter:@document \
  --output-dir build/article \
  --build
```

Need a blank template skeleton? Use the scaffold flag to copy any template into
your working tree:

```bash
texsmith --template article --template-scaffold my-template
cd my-template
uv run hatch build  # optional packaging smoke test
```

Publish by pointing `pyproject.toml` to the `template/` package, then `uv publish` or `twine upload dist/*`.
For in-depth patterns (overrides, slots, metadata), see the Template Cookbook.

= Write your own TeXSmith templates

TeXSmith uses Jinja2 templates to assemble #ts-logo("LaTeX") documents from converted
Markdown fragments. You can create your own templates to control the layout,
styling, and structure of the final output.

You may start by copying an existing template package and modifying it to suit
your needs. Templates can either be published on PyPI for easy distribution or kept locally for personal use. By default, TeXSmith will look for templates installed in the current Python environment or in the current working directory under a `templates/` folder.

== Structure

```
├── README.md
├── __init__.py          # optional: a WrappableTemplate subclass, custom normalisers
├── pyproject.toml       # only to publish the template as a package
└── template
    ├── assets
    │   └── latexmkrc
    ├── manifest.toml
    ├── template.tex     # the LaTeX entrypoint
    ├── template.typ     # optional: the Typst scaffolding, [typst.template]
    ├── mermaid-config.json  # optional
    └── .sty, .cls...
```

`texsmith –template article –template-scaffold DEST` writes exactly this
shape for a built-in, which is the quickest way to see a real one.

== TOML manifest

The `manifest.toml` file describes the template and its metadata.

```toml
[compat]
# Specify the compatible TeXSmith versions. Do not forget
# to set a maximum version to avoid future incompatibilities.
texsmith = ">=0.1,<1.0"

[latex.template]
name = "acme"
version = "0.1.0"
entrypoint = "template/template.tex"
# IR passes this template needs, resolved with the same import machinery as
# attribute normalisers and applied only while this template renders.
passes = ["acme_pkg.questions:run"]
# Useful for generic docker images or CI pipelines, where
# we only install the required packages.
texlive_year = 2023
tlmgr_packages = [
    "babel",
    "geometry",
    "hyperref",
    "microtype",
    "fontspec",
    "biblatex",
]

# Attributes:
# -----------
# Attributes are declared as nested tables describing the type, default
# value, and optional normalisation rules for each entry. Types are inferred
# from the default when omitted.
[latex.template.attributes.base_level]
default = 1
type = "integer"

[latex.template.attributes.title]
default = "Title"
type = "string"
escape = "latex"
allow_empty = false

[latex.template.attributes.subtitle]
default = ""
type = "string"
escape = "latex"

[latex.template.attributes.author]
default = "John Doe"
type = "string"
escape = "latex"

[latex.template.attributes.date]
default = "\\today"
type = "string"
escape = "latex"

[latex.template.attributes.language]
default = "english"
type = "string"
normaliser = "babel_language"

[latex.template.attributes.paper]
default = "a4paper"
type = "string"
normaliser = "paper_option"

[latex.template.attributes.orientation]
default = "portrait"
type = "string"
normaliser = "orientation"
choices = ["portrait", "landscape"]

[latex.template.attributes.bibliography_style]
default = "numeric"
type = "string"

# Slots definition:
# -----------------
# Each slot represents a section of the document that can be filled
# with content. The 'depth' parameter indicates the LaTeX sectioning
# command to use.
[latex.template.slots.mainmatter]
default = true
depth = "section"

[latex.template.slots.abstract]
depth = "section"
strip_heading = true

# Additional Assets:
# ------------------
# All additional assets to be included in the template package.
# They will be copied to the working directory when the template is used.
[latex.template.assets]
".latexmkrc" = { source = "template/assets/latexmkrc" }

# The Typst half, for a template that also serves --format typst. Same shape:
# its own entrypoint, attributes and slots. A template without it still
# renders to Typst, in the standalone preamble.
[typst.template]
entrypoint = "template/template.typ"
```

=== Attribute schema

Each attribute table accepts the following keys:

- `default`: (required) the value injected when no override is provided.
- `type`: optional primitive among `string`, `integer`, `float`, `boolean`, `list`, `mapping`, `any`. When omitted TeXSmith infers a type from `default`.
- `sources`: the lookup paths (dot notation) used to pull overrides from document front matter. If omitted, TeXSmith probes `press.press.<name>`, `press.<name>`, then `<name>`.
- `allow_empty`: when `false`, empty strings are coerced to `None` so templates fall back to defaults.
- `required`: when `true`, a missing override raises a `TemplateError`.
- `choices`: restricts string/integer values to the provided list.
- `escape`: currently supports `latex` to automatically escape special characters coming from user input.
- `normaliser`: a built-in normaliser name *or* a `"module:callable"` import reference pointing at your own callable that post-processes the value (see below).

Attributes are resolved before `WrappableTemplate.prepare_context` runs, meaning template classes only need to handle presentation-specific tweaks (for example, combining authors, building option strings, or removing temporary keys).

== Attribute ownership & precedence

- Each attribute belongs to a single owner (template by default, fragment when declared in `fragment.toml`). Conflicting owners raise a `TemplateError`.
- Overrides flow: CLI/front matter #ts-script("symbols")[→ ]attribute resolver (type coercion, normalisers) #ts-script("symbols")[→ ]template emitters/fragment defaults. Empty strings are dropped when `allow_empty = false`.
- Attributes no longer live under ad-hoc dotted names (`press.*`); normalisation collapses supported aliases onto the declared attribute name.

== Template slots and built-ins

- Templates must declare at least one slot; `mainmatter` is the default when absent. Slots surface `depth`, `offset`, `strip_heading`, and optional `base_level`.
- Built-in `article` exposes `mainmatter`, `abstract`, `appendix`, and `backmatter`. `book` inserts `appendix` before `backmatter` and supports `part` toggling. `letter` uses `mainmatter` only.
- Deprecated attributes removed from built-ins: `article`/`book` no longer accept `cover`, `covercolor`, `twocolumn`, or template-owned `emoji`. Backmatter/preamble overrides moved into fragments where applicable.

=== Built-in normalisers

#table(
columns: 2,
align: (left, left),
table.header([Name], [Purpose]),
[`paper_option`], [Validates paper sizes and emits `<size>paper` strings (for example `letterpaper`).],
[`orientation`], [Normalises orientation flags and guarantees `portrait` or `landscape`.],
[`babel_language`], [Maps ISO-like language codes to Babel identifiers (for example `fr` #ts-script("symbols")[→ ]`french`).],
)

Normalisers run after type coercion and before escaping. They can also reuse existing defaults to provide fallbacks (`paper_option` and `orientation` do this).

=== Custom normalisers from template packages

Beyond the built-in names, `normaliser` accepts a fully-qualified callable
reference so a template package can supply its own normaliser without touching
TeXSmith internals. Use the `"package.module:callable"` form (the dotted
`"package.module.callable"` form is also accepted):

```toml
[latex.template.attributes.rules]
type = "any"
normaliser = "texsmith_template_exam.rules:resolve_attribute"
```

The referenced object is imported (and cached) when the manifest is loaded, and
must honour the normaliser contract:

```python
def resolve_attribute(value, spec, fallback):
    # value:    the already type-coerced attribute value
    # spec:     the TemplateAttributeSpec (use spec.name in error messages)
    # fallback: the attribute's resolved default
    # returns:  the normalised value
    ...
```

If the module or attribute cannot be found, or the target is not callable,
TeXSmith raises a `TemplateError` naming the offending template, attribute, and
`normaliser` value.

Authors who prefer a short registry name can instead call
`texsmith.core.templates.register_attribute_normaliser(name, func)` at import
time and reference it by `name`. Registering over a built-in name raises a
`TemplateError` unless `override=True` is passed. The `"module:callable"` form is
collision-free and needs no registration, so it is generally preferred.

=== Metadata overrides

At runtime TeXSmith merges template defaults with document front matter. By default, overrides come from the `press` section:

```yaml
---
press:
  title: Sample Article
  subtitle: Insights on Cheese
  language: fr
  authors:
    - name: Ada Lovelace
      affiliation: Analytical Engine
    - name: Grace Hopper
---
```

With the manifest above TeXSmith will:

- Escape `title` and `subtitle` for #ts-logo("LaTeX") compatibility.
- Map `language: fr` to `french`.
- Normalise author collections so individual templates can format them consistently.
- Populate both defaults (`author`) and structured data (`authors`) that template classes can consume.

To pull metadata from alternative locations add explicit `sources`:

```toml
[latex.template.attributes.project_code]
default = ""
type = "string"
sources = ["press.project.code", "project.code"]
allow_empty = false
```

=== Slots

Slots control where converted content is injected. Each entry allows:

- `depth`: maps to a #ts-logo("LaTeX") sectioning command (`section`, `chapter`, etc.).
- `base_level` and `offset`: fine tune heading levels when rendering.
- `default`: mark exactly one slot as the primary sink for content.
- `strip_heading`: remove the first heading when populating the slot (useful for abstracts).

Slots become Jinja variables inside the template (`\VAR{abstract}`, `\VAR{mainmatter}`).

== Overrides

The #ts-logo("LaTeX") body comes from tmark's writer, which emits a fixed macro or
environment per construct. Structural constructs (emphasis, lists, headings,
figures, tables, links, footnotes) are plain #ts-logo("LaTeX") the writer owns; everything a
template may want to restyle is a *contract macro* provided by a `ts-*`
fragment. Redefine it in your template's `.tex`, after `\VAR{extra_packages}`
(that is where the fragments are `\usepackage`d):

```latex
\VAR{extra_packages}
\tcbset{/ts/code/.append style={frame hidden, boxrule=0pt}}
\RenewDocumentCommand{\tscodeinline}{O{}m}{\texttt{#2}}
\RenewDocumentEnvironment{tsdiv@multicolumn}{O{}}{\begin{multicols}{3}}{\end{multicols}}
```

See Contract macros for the full table of macros, their keys and
the three levels of override.

#ts-callout(kind: "warning", title: [Jinja partials are no longer the rendering layer])[
`latex.template.override`, fragment `partials` and `required_partials` were
deprecated in 0.7.0 and are removed in 0.8.0: the manifest no longer reads
them. #link("partials.md#former-partials")[Contract macros] maps every former
partial to its replacement macro.]

== Slot strategies

Slots determine how multiple Markdown documents (or sections) flow into the
#ts-logo("LaTeX") structure. Typical patterns:

- *Single document, single slot* – map the only input with `–slot mainmatter:@document`.
- *Front matter + main matter* – convert two files (eg `intro.md`,
`book.md`) and pass `–slot frontmatter:intro.md` and `–slot mainmatter:book.md`.
- *Selective sections* – reference headings or IDs:
`–slot abstract:paper.md:@abstract –slot mainmatter:paper.md:"Results"` injects
only the abstract heading and the “Results” section into separate slots.
- *Per-language appendices* – define slots (`appendix_en`, `appendix_fr`) and use front-matter metadata (`press.slot.appendix_en: docs/en.md`) so automation scripts do not need to pass CLI flags.

Slots are resolved by the document slot mapping across CLI flags, front matter (`press.slot.*`), and API overrides, so mix and match whichever suits your workflow.

== Testing your template

Before publishing, run the built-in test suite against your template:

```bash
uv run pytest tests/test_template_attributes.py
```

This repository includes examples for the bundled templates; copy one into your package and adjust expectations to match your manifest. Automated tests help ensure attributes, slots, and metadata mappings keep working as the TeXSmith runtime evolves.

= Next steps

- Study the Template Cookbook for practical recipes (title pages, metadata bindings, bibliography tweaks).
- Browse the API high-level guide to orchestrate templates programmatically with `ConversionService`.
