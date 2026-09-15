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
#text(size: 1.8em, weight: "bold")[Diagrams]]
#v(1.5em)

#ts-callout-style.update("fancy")

Markdown doesn’t have to be flat text. Here’s how we wire live #link("https://mermaid.js.org/")[Mermaid] and #link("https://app.diagrams.net/")[Draw.io] diagrams straight into TeXSmith, no opaque binaries, friendly diffs.

#figure(
image("snippet-<HASH>.pdf", width: 60%),
)

Here is the source:

````markdown
---
press:
  subtitle: "An Overview of drawio and mermaid diagram integration"
  paper:
    margin: 2cm
---
# Diagram Integration

You can embed Draw.io or Mermaid diagrams directly in Markdown. This keeps
technical documentation close to the visuals it describes, and the package
takes care of converting each diagram to an image that the final LaTeX
document can reference automatically.

## Draw.io Diagram

![Euclidean GCD](pgcd.drawio){width=60%}

Figure: Euclidean algorithm for the greatest common divisor

## Mermaid Diagram

```mermaid image width="80%"
%% Vegetable harvesting algorithm
flowchart LR
    start(Start) --> pick[Dig up]
    pick --> if{Cabbages?}
    if --No--> step[Move forward one step]
    step --> pick
    if --Yes--> stop(End)
```
````

= Rendered Markdown

Obviously everything built with TeXSmith can also be rendered in this very Markdown file:

== Draw.io Diagram

#figure(
image("pgcd.pdf"),
caption: [Euclidean algorithm for the greatest common divisor.],
) <fig:pgcd>

== Mermaid Diagram

A bare `mermaid` fence is sugar for `mermaid image` and is kept indefinitely,
because that is what MkDocs Material renders natively.

#figure(
image("<HASH>.pdf"),
caption: [Vegetable harvesting algorithm],
)

= Draw.io backend choice

TeXSmith now tries a Playwright-based exporter first (cached under `~/.cache/texsmith/playwright`), falling back to the local `drawio`/`mmdc` CLI and finally the Docker image. Force a specific path with `–diagrams-backend=playwright|local|docker` if needed.
