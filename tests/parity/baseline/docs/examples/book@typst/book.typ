#set document(
title: "Book",
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
#text(size: 1.8em, weight: "bold")[Book]]
#v(1.5em)

#ts-callout-style.update("fancy")

#metadata(none) <einstein>

For this example we want to render homage to Albert Einstein by creating a small book using the #link("https://en.wikipedia.org/wiki/Albert_Einstein")[Wikipedia]
as our source.

The text was converted to #ts-logo("LaTeX") then built using the `book` template.

This example demonstrates the use of front matter for citations, abbreviations, glossary, and index.

For this example, we decided to use a small paper size (A5) and a sans serif font (Adventor). The book is structured in parts and specific slots are used for the colophon, dedication, and preface. Here is the front matter used for this example:

```yaml
title: Albert Einstein
subtitle: His Life and Achievements
date: 2025-03-15
edition: Wikipedia Adaptation
author: Wikipedia Contributors
publisher: Wikipedia Sourcebooks
imprint:
  thanks: |
    Adapted from the Wikipedia article “Albert Einstein” (retrieved ).
    Thank you to the Wikipedia contributors whose work makes this example
    possible.
  copyright: |
    Wikipedia contributors. Text licensed under Creative Commons Attribution-ShareAlike
    International (CC BY-SA).
  license: |
    This TeXSmith example is derived from Wikipedia and is not affiliated
    with TeXSmith. Reuse must credit Wikipedia and share under CC BY-SA .
press:
  paper: a5
  template: book
  base_level: part
  fonts: adventor
  callouts:
    style: classic
  slots:
    colophon: Colophon
    dedication: Dedication
    preface: Preface
```

#figure(
image("snippet-<HASH>.pdf"),
)

The example can be built independently using the CLI in the `examples/book/` folder. The engine can be chosen between `tectonic`, `xelatex`, and `lualatex`
as follows:

```bash
texsmith book.md <STEM>.bib --template book --build --engine tectonic
```

The power of TeXSmith is that it can generate such complex documents from simple Markdown with no #ts-logo("LaTeX") knowledge required and no #ts-logo("LaTeX") toolchain installed. Fonts, toolchain, and image conversion are all handled automatically by TeXSmith in a single command.
