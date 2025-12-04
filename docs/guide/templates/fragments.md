# Template fragments

Fragments are small, pluggable LaTeX packages (`.sty` rendered from Jinja) that
TeXSmith can inject into any template at `\VAR{extra_packages}`. They keep
shared logic (callouts, code listings, …) out of individual templates
while staying configurable from front matter or your own extensions.

## Built-in fragments

`ts-geometry`
: page size/orientation glue that mirrors `press.paper`/`press.geometry` options.

`ts-extra`
: opt-in aux packages detected from the rendered content (hyperref, soul, ulem, etc.).

`ts-keystrokes`
: renders `\keystroke{…}` shortcuts with styled TikZ boxes when they appear in content.

`ts-callouts`
: admonition/callout boxes generated from callout definitions.

`ts-code`
: unified minted/tcolorbox code listing style.

`ts-index`
: central imakeidx/macros glue, selects texindy/makeindex and runs `\makeindex` when entries are present.

`ts-glossary`
: glossary and acronym wiring: loads `glossaries`, runs `\makeglossaries` when needed, and materialises acronym definitions from front matter with configurable styles.

`ts-bibliography`
: bibliography helper that wires `biblatex` into the rendered document.

`ts-todolist`
: checklist helpers providing `\done`, `\wontfix`, and the `todolist` environment when they are referenced.

All built-in templates default to rendering these fragments. They are
written into the build directory as `ts-*.sty` and loaded via
`\usepackage{...}` in the generated TeX.

## Using fragments in documents

Fragments are declared under the `press.fragments` list in front matter. Each
entry is either the name of a built-in fragment or a path to a custom Jinja
template (absolute or relative to the Markdown file).

```yaml
---
press:
  template: article
  fragments:
    - ts-callouts
    - ts-code
    - ts-glossary
    - fragments/foo.jinja.sty  # custom fragment located next to your doc
  foo:
    value: 42         # variables consumed by foo.jinja.sty
---
```

TeXSmith renders each fragment into the output directory and injects the
corresponding `\usepackage{…}` lines into `\VAR{extra_packages}`.

### What a fragment looks like

Fragments are plain Jinja templates that output LaTeX. The package name is the
stem of the file unless it is a built-in registered name.

```tex
% fragments/foo.jinja.sty
\ProvidesPackage{foo}[2025/01/01 Example fragment]
\newcommand{\FooValue}{\VAR{foo.value|default(0)}}
```

With the front matter above, the generated build will contain `foo.sty` and the
document preamble will include `\usepackage{foo}`.

## Template authors: allowing fragments

To consume fragments, a template needs a placeholder where TeXSmith can inject
the `\usepackage` lines. Add `\VAR{extra_packages}` near the top of your
preamble—typically next to other package imports. No TOML manifest changes are
required; the core runtime resolves fragments before rendering.

Built-in templates already include this placeholder and opt into
`ts-geometry`, `ts-extra`, `ts-keystrokes`, `ts-callouts`, `ts-code`,
`ts-glossary`, `ts-index`, `ts-bibliography`, and `ts-todolist` via the template
runtime extras; conditional fragments only render when their macros are present
in the rendered LaTeX. Third-party templates can also declare default fragments
in their `TemplateRuntime.extras["fragments"]` or let users supply their own
through front matter.

### Passing variables to fragments

Any values under `press` (or other front-matter keys) are merged into the
template rendering context. If your fragment expects a variable such as
`foo.value`, document it and read it directly in the Jinja template. Unknown
keys are ignored.

## CLI and API integration

CLI usage is automatic once `press.fragments` is present. For API consumers:

```python
from texsmith.api import Document, TemplateSession
from texsmith.core.templates import load_template_runtime

session = TemplateSession(load_template_runtime("article"))
session.add_document(Document.from_markdown(path_to_md))
result = session.render(output_dir)
# result.main_tex_path already includes the rendered fragments
```

Custom fragments may live anywhere; relative paths are resolved against the
document’s directory. Built-in names are always available without shipping
assets in your template package.
