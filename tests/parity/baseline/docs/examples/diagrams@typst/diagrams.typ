#set document(
  title: "Diagrams",
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
  #text(size: 1.8em, weight: "bold")[Diagrams]
]
#v(1.5em)

Markdown doesn’t have to be flat text. Here’s how we wire live #link("https://mermaid.js.org/")[Mermaid] and #link("https://app.diagrams.net/")[Draw.io] diagrams straight into TeXSmith, no opaque binaries, friendly diffs.

Here is the source:

```markdown

```

= Rendered Markdown

Obviously everything built with TeXSmith can also be rendered in this very Markdown file:

== Draw.io Diagram

#figure(
  image("<HASH>.png"),
  caption: [Euclidean algorithm for the greatest common divisor],
)

== Mermaid Diagram

#figure(
  image("<HASH>.png"),
  caption: [Vegetable harvesting algorithm],
)

= Draw.io backend choice

TeXSmith now tries a Playwright-based exporter first (cached under `~/.cache/texsmith/playwright`), falling back to the local `drawio`/`mmdc` CLI and finally the Docker image. Force a specific path with `--diagrams-backend=playwright|local|docker` if needed.
