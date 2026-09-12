#set document(
title: "Welcome to TeXSmith",
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
#text(size: 1.8em, weight: "bold")[Welcome to TeXSmith]]
#v(1.5em)

*TeXSmith* turns #link("https://www.markdownguide.org/")[Markdown] into
press-ready #link("https://www.latex-project.org/")[#ts-logo("LaTeX")]. Keep your
docs authored in Markdown, then compile polished PDFs for print,
journals, or long-form review packages—without maintaining several sources of truth. No need to learn #ts-logo("LaTeX"), install heavy toolchains, or wrestle with complex conversion setups.

#box(image("ts-light.svg", width: 50%))
#box(image("ts-dark.svg", width: 50%))

Furthermore, TeXSmith is optimized for MkDocs thanks to the TeXSmith MkDocs plugin, which seamlessly integrates into your documentation pipeline.

#ts-callout(kind: "danger", title: [Currently in Alpha])[
TeXSmith is currently in Alpha. While we are actively working on it and
welcome feedback, please be aware that some features may not be fully stable yet.]

You can use TeXSmith to generate academic papers, technical reports, letters,
minutes, or class materials with diagrams, tables, citations, and more.

#figure(
image("pipeline.png"),
caption: [Pipeline],
)

= Why would I use TeXSmith?

TeXSmith bridges the gap between lightweight Markdown authoring
and the typographic power of #ts-logo("LaTeX"). It is ideal for:

- Writing scientific articles.
- Writing product documentation.
- Writing books.
- Writing letters.
- Writing technical reports.
- Writing cooking recipes and more.

The combination with MkDocs provides a single source of truth for both web and PDF output, which improves collaboration because all documentation lives in Markdown in a Git repository. Versioning with MkDocs stays simple and natural.

= Why teams choose TeXSmith

/ Pipeline parity: The CLI and Python API share the same conversion engine,

so automation scripts and ad-hoc conversions stay in sync.

/ Template-friendly: Wrap multiple documents into a single #ts-logo("LaTeX") project, map bodies into template

slots, and restyle any construct by redefining its contract macro.

/ Diagnostics you can trust: Structured emitter APIs and CLI verbosity

flags surface the context you need when something goes wrong.

= The dialect

TeXSmith reads TMark: #link("https://commonmark.org/")[CommonMark],
plus the extension set every MkDocs site already loads, plus exactly four
syntactic families for what print needs — attributes, roles, container
directives and data directives — and two sigils: *`#` defines, `@` refers*.

```md
See @fig:trace and @sec:boot; the measurement is from @ein05.

![Trace](trace.png){width=60%}

Figure: The watchdog firing twice. {#fig:trace}

::: warning {title="LaTeX toolchain"}
Install TeX Live before `texsmith --build`.
:::
```

It has a specification, a parser, a canonical printer and a linter, so
`tmark check FILE` tells you exactly what the converter read, and
`tmark lint –fix FILE` rewrites an older document into the canonical spelling.
Upgrading from TeXSmith 0.6? See Migrating to TMark.

= How is it different from Pandoc?

#link("https://pandoc.org/")[Pandoc] is a powerhouse, but reproducing an extended
Markdown dialect in Pandoc requires custom filters and ongoing maintenance.
TeXSmith delivers parity with the MkDocs world out of the box:

- Handles Material-only components such as tabbed content, callouts, and
keyboard keys.
- Ships with diagram converters (Mermaid, Draw.io) that plug directly
into the #ts-logo("LaTeX") build step.
- Exposes the same primitives via the CLI and Python API, so automation scripts
match what authors do locally.
- Every construct says how it degrades elsewhere, and Pandoc's own citation
grammar is accepted for import.

Use both tools together when it makes sense; reach for TeXSmith when MkDocs #ts-script("symbols")[→ ]#ts-logo("LaTeX")
compatibility is the priority.
