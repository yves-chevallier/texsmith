#set document(
title: "Template fragments",
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
#text(size: 1.8em, weight: "bold")[Template fragments]]
#v(1.5em)

#ts-callout-style.update("fancy")

Fragments are small, pluggable #ts-logo("LaTeX") packages (`.sty` rendered from Jinja) that
TeXSmith can inject into any template at `\VAR{extra_packages}`. They keep
shared logic (callouts, code listings, …) out of individual templates
while staying configurable from front matter or your own extensions.

= Built-in fragments

Most built-in fragments are *contract fragments*: they define the macros
the tmark writer emits for a construct (`\tsmark`, `tscallout`, `tscode`,
`\tskeys`, …), listed per fragment in `tmark.fragments()` and documented in
Contract macros. A contract fragment is activated by the writer:
a body that emits `\begin{tscallout}` names `ts-callouts` in its
`Requires.fragments`, and TeXSmith renders it — by construction, never by
sniffing the emitted #ts-logo("LaTeX") for a macro name. The remaining fragments are
configuration and render when their options say so.

/ `ts-geometry`: page size/orientation glue that mirrors `press.paper`/`press.geometry` options. Configuration, not a contract.
/ `ts-typesetting`: paragraph spacing, leading and line numbers (when configured), and the

contract macros `\tslead`, `\tsmark`, `\tsdivider`, `\tsrule`, `\tsepigraph`,
`\tsaside`, `\tsprogress`, `\tsicon`, `\tslogo` and the `tsdiv` container.

/ `ts-fonts`: font selection driven by `fonts.family`, script fallback fonts, and the

`\tsscript` / `\tsemoji` switches.

/ `ts-extra`: aux packages: the writer's `Requires.packages` minus the packages the active

contract fragments already load.

/ `ts-keystrokes`: `\tskeys{Ctrl,Alt,Del}` as styled TikZ boxes, one per key, joined by `+`.
/ `ts-callouts`: the `tscallout` environment, generated from the callout definitions

(built-in and `press.declare.admonitions`) and the `press.callouts.*` colours,
icons and style.

/ `ts-code`: the `tscode` environment and `\tscodeinline`, over pygments, minted, listings

or fvextra according to `code.engine`.

/ `ts-critic`: critic markup: `\tsins`, `\tsdel`, `\tssubst`, `\tscomment`.
/ `ts-index`: `\tsindex`, central imakeidx glue, one `\makeindex[name=…]` per registry of

`Requires.index`, texindy/makeindex selection.

/ `ts-glossary`: `\tsgls` / `\tsacr` and the glossary wiring: loads `glossaries`, runs `\makeglossaries` when needed, and materializes acronym definitions from front matter with configurable styles.
/ `ts-bibliography`: `\parencite` / `\textcite` fallbacks when no `.bib` loaded `biblatex`, plus

the bibliography wiring. By default, raw URLs in entries are suppressed and
the entry title becomes a clickable hyperlink to the entry's `url` field —
this avoids the overfull/underfull `\hbox` warnings that long URLs typically
cause in justified bibliographies. Set `bibliography_show_urls: true` in the
document front matter to print the full URL inline instead (same behaviour
as biblatex's stock styles).

/ `ts-todolist`: the `tstasklist` environment and its `\tsdone`, `\tstodo` and `\tspartial`

markers, for a Markdown task list.

/ `ts-frame`: an optional page frame with an optional folded corner (`press.frame`).

Configuration, not a contract; the snippet previews in this documentation use
it.

Templates default to the contract fragments plus the configuration ones they
need. Each is written into the build directory as `ts-*.sty` and loaded via
`\usepackage{…}` at `\VAR{extra_packages}`.

= Using fragments in documents

Fragments are declared under the `press.fragments` key in front matter. Each
entry is either the name of a built-in fragment or a path to a custom Jinja
template (absolute or relative to the Markdown file).

== Explicit list (replaces template defaults)

Provide a plain list to replace the template's default fragment set entirely:

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

== Modifier dict (extends template defaults)

When you only need to add or remove a few fragments without restating the full
list, use the dict form with any combination of `append`, `prepend`, and
`disable`:

```yaml
---
press:
  template: article
  fragments:
    append:
      - ./fragments/heiglogo   # add a custom fragment at the end
    prepend:
      - ./fragments/header     # add a fragment at the start
    disable:
      - ts-geometry            # remove a specific built-in fragment
---
```

All three keys are optional. Omitted keys leave the corresponding part of the
default list unchanged. `disable` is applied first (before `prepend`/`append`),
so the same fragment cannot appear in both `disable` and `prepend`/`append`.
`–enable-fragment` / `-f` and `–disable-fragment` / `-F` apply the same two
operations from the command line.

Disabling a *contract* fragment does not remove it: the writer still names it
in `Requires.fragments`, so the macros the body emits stay defined. To change
what a construct looks like, redefine its contract macro or replace the
fragment with one that provides the same list — see
#link("partials.md#overriding-a-construct")[Contract macros].

TeXSmith renders each fragment into the output directory and injects the
corresponding `\usepackage{…}` lines into `\VAR{extra_packages}`.

== What a fragment looks like

Fragments are plain Jinja templates that output #ts-logo("LaTeX"). The package name is the
stem of the file unless it is a built-in registered name.

```tex
% fragments/foo.jinja.sty
\ProvidesPackage{foo}[2025/01/01 Example fragment]
\newcommand{\FooValue}{\VAR{foo.value|default(0)}}
```

With the front matter above, the generated build will contain `foo.sty` and the
document preamble will include `\usepackage{foo}`.

= Template authors: allowing fragments

To consume fragments, a template needs a placeholder where TeXSmith can inject
the `\usepackage` lines. Add `\VAR{extra_packages}` near the top of your
preamble—typically next to other package imports. No TOML manifest changes are
required; the core runtime resolves fragments before rendering.

Built-in templates already include this placeholder and declare their default
fragment set through the template runtime extras; a contract fragment renders
only when a body's `Requires.fragments` names it, so a document without code
carries no `ts-code.sty`. Third-party templates can declare their own defaults
in `TemplateRuntime.extras["fragments"]`, or let users supply theirs through
`press.fragments` and `-f` / `-F` on the command line.

== Passing variables to fragments

Any values under `press` (or other front matter keys) are merged into the
template rendering context. If your fragment expects a variable such as
`foo.value`, document it and read it directly in the Jinja template. Unknown
keys are ignored.

= CLI and API integration

CLI usage is automatic once `press.fragments` is present. For API consumers:

```python
from texsmith import Document, TemplateSession
from texsmith.core.templates import load_template_runtime

session = TemplateSession(load_template_runtime("article"))
session.add_document(Document.from_markdown(path_to_md))
result = session.render(output_dir)
# result.main_tex_path already includes the rendered fragments
```

Custom fragments may live anywhere; relative paths are resolved against the
document’s directory. Built-in names are always available without shipping
assets in your template package.
