#set document(
title: "Extending TeXSmith",
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
#text(size: 1.8em, weight: "bold")[Extending TeXSmith]]
#v(1.5em)

TeXSmith's dialect is TMark, and TMark is a *closed*
language: the four syntactic families, the role registry and the container
registry do not grow per project. That is the point — a construct you have never
seen is still readable, and a document still renders somewhere else.

So "writing an extension" is not "adding syntax". It is one of four things:

#table(
columns: 2,
align: (left, left),
table.header([You want to…], [Do this]),
[add a new _kind_ of callout (Solution, Exercise, Risk)], [declare it under `press.declare.admonitions`],
[add a new numbered series (findings, requirements)], [declare it under `press.declare.counters`],
[wrap content in something the template styles], [use `::: div {.class}` and style the class],
[compute something at build time (fetch, convert, execute)], [write an *IR pass*],
[change how a construct _looks_], [redefine its *contract macro*, or replace the fragment],
)

The first two are pure front matter and need no code:
#link("../syntax/admonitions.md#custom-types")[Admonitions] and
Custom counters.

= Containers

A container is the escape hatch for structure. The container names TMark knows
are a *closed* registry — the callout types (built-in and declared), `aside`,
`figure`, `tabs`, `tab`, `multicolumn` and `div` — and there is deliberately no
mechanism to add a name: a template that renders a name the registry does not
know has extended the language.

`::: div` is the container that means nothing: a hook for classes and an id.

```md
::: div {#s1 .sidebar}
Content the template lays out.
:::
```

Every layout container lowers to one contract on the paged backends —
`\begin{tsdiv}{name}[attrs]`, `#ts-div("name", ..)` — dispatched on the name,
with `#id` forwarded as `id`, classes as `class={a,b}` and `key=val` as is
(`lang` and `media` never). Style the class:

```latex
\tcbset{/ts/div/class/sidebar/.style={grow to left by=2cm}}
```

On the web the same container is `<div class="sidebar">`, which is exactly what
a site stylesheet needs. A name the registry does not know raises
`container-unknown` and renders its content transparently, rather than silently
becoming an unstyled `<div>`.

= IR passes

Anything that has to _compute_ — read a file, convert a diagram, call a
network service, execute a fence — is a pass: a pure function
`(Document, PassContext) -> Document` over the IR, running either before
`tmark.resolve` (`pre`) or after it (`post`).

```python
from texsmith.core.documents import Document
from texsmith.passes import PassContext, spec

@spec("exam-questions", stage="pre", after=("include",))
def run(document: Document, ctx: PassContext) -> Document:
    ...
```

Declare a template's passes in its manifest so they apply only while that
template renders:

```toml
[latex.template]
passes = ["my_exam_pkg.questions:run"]
```

The full contract — ordering, diagnostics, the rules a pass must not break — is
in IR passes and fragment contracts.

= Fragments and contract macros

The writers emit a fixed macro or environment per construct (`\tslead`,
`\tsaside`, `\tskeys`, `tscallout`, `tscode`, …), and a fragment must define
every macro the writer can name. Restyle through the `pgfkeys` family, redefine
the macro with the same signature, or replace the fragment outright:

```yaml
press:
  fragments:
    disable: [ts-code]
    append: [./my-code.sty]
```

See Contract macros for the construct-to-macro table
and Fragments for how a fragment is built.

On a MkDocs site the index entries reach `search_index.json` through the
`texsmith` plugin, which collects them from the rendered pages
and injects them after the `search` plugin wrote its index. The separate
`texsmith.index` MkDocs _plugin_ is deprecated — it warns and does nothing, and
disappears in 0.8; the `texsmith.index` _Markdown extension_ above is
unaffected.

#ts-callout(kind: "note", title: [The Python-Markdown extensions are transitional])[
`texsmith.extensions.*` still ships the Python-Markdown implementations of
the 0.6 syntax (`smallcaps`, `latex_raw`, `multi_citations`, `mermaid`,
`index`, `counters`, …) so that an existing MkDocs site keeps building
during the migration. They are not the conversion path any more — TeXSmith
parses with tmark — and they are removed in 0.8.0 together with the
spellings they implement. See Migrating to TMark.]

= Inspecting what the parser read

```bash
tmark parse report.md      # the IR as JSON
tmark check --strict FILE  # parse, resolve and lint
tmark write --to latex --map FILE  # the body, its source map and its Requires
```

`Requires` is what a construct demands of the template: packages, fragments,
shell escape, assets, citations, index registries, counter series. If your
extension needs the template to do something, that is where it says so.
