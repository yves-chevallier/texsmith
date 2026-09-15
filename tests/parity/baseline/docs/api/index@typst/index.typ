#set document(
title: "TeXSmith API Overview",
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
#text(size: 1.8em, weight: "bold")[TeXSmith API Overview]]
#v(1.5em)

#ts-callout-style.update("fancy")

The API reference is generated with *mkdocstrings* to stay in sync with the codebase. This section is organized into themed pages so you can quickly locate the module you need.

Each page uses `::: module.path` directives; mkdocstrings resolves them at build time and renders docstrings, signatures, and cross-references.

= API Sections

/ `high-level`: High-level orchestration helpers (`ConversionService`, `TemplateSession`) for programmatic conversions and template sessions.
/ `core`: Core package modules (`texsmith`, configuration, contexts, conversion helpers, etc.).
/ `bibliography`: Bibliography tooling (#ts-logo("BibTeX") parsing, DOI resolution, issue reporting).
/ `cli`: Command-line entry points and utilities.
/ `handlers`: IR passes and fragment contracts — the two extension points of the `parse → IR → passes → resolve → write` pipeline.
/ `latex`: #ts-logo("LaTeX") infrastructure (formatter, escaping, templates).
/ `plugins`: Optional integrations (MkDocs Material-specific handlers).
/ `transformers`: Asset conversion strategies (SVG, Draw.io, Mermaid, remote images).

Use the navigation sidebar to jump to any section or follow the links above for more detail.
