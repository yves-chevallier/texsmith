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
  #text(size: 1.8em, weight: "bold")[Welcome to TeXSmith]
]
#v(1.5em)

*TeXSmith* turns #link("https://www.markdownguide.org/")[Markdown] into
press-ready #link("https://www.latex-project.org/")[LaTeX]. Keep your
docs authored in Markdown, then compile polished PDFs for print,
journals, or long-form review packages—without maintaining several sources of truth. No need to learn LaTeX, install heavy toolchains, or wrestle with complex conversion setups.

Furthermore, TeXSmith is optimized for MkDocs thanks to the TeXSmith MkDocs plugin, which seamlessly integrates into your documentation pipeline.

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#C62828"), rest: 0.4pt + rgb("#C62828")))[
  #block(width: 100%, fill: rgb("#C62828").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#C62828"))[🔥#h(0.4em)Currently in Alpha]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    TeXSmith is currently in Alpha. While we are actively working on it and
    welcome feedback, please be aware that some features may not be fully stable yet.
  ]
]

You can use TeXSmith to generate academic papers, technical reports, letters,
minutes, or class materials with diagrams, tables, citations, and more.

#figure(
  image("pipeline.png"),
  caption: [Pipeline],
)

= Why would I use TeXSmith?

TeXSmith bridges the gap between lightweight Markdown authoring
and the typographic power of LaTeX. It is ideal for:

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
/ Template-friendly: Wrap multiple documents into a single LaTeX project,
  map fragments into template slots, and customise the runtime with Jinja2.
/ Diagnostics you can trust: Structured emitter APIs and CLI verbosity
  flags surface the context you need when something goes wrong.

= How is it different from Pandoc?

#link("https://pandoc.org/")[Pandoc] is a powerhouse, but reproducing an extended Markdown syntax other than
#link("https://commonmark.org/")[CommonMark] or #link("https://github.github.com/gfm/")[GitHub-flavored Markdown] document in
Pandoc requires custom filters and ongoing maintenance. TeXSmith focuses on MkDocs Markdown
with Pymdown extensions, delivering parity out of the box:

- Handles Material-only components such as tabbed content, callouts, and
    keyboard keys.
- Ships with diagram converters (Mermaid, Draw.io) that plug directly
    into the LaTeX build step.
- Exposes the same primitives via the CLI and Python API, so automation scripts
    match what authors do locally.

Use both tools together when it makes sense; reach for TeXSmith when MkDocs → LaTeX
compatibility is the priority.
