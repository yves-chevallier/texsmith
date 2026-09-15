#set document(
title: "Examples",
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
#text(size: 1.8em, weight: "bold")[Examples]]
#v(1.5em)

#ts-callout-style.update("fancy")

Great documentation shines brightest with real examples — so here are a few to get you started. These showcase TeXSmith’s range across various document types and creative workflows:

- Letters
- Books
- Custom posters
- Cooking recipes
- Diagrams
- Academic articles
- Snippet blocks for embedding PDF previews
- ...

Each example lives in its own folder inside the `examples/` directory of the #link("https://github.com/yves-chevallier/texsmith/tree/master/examples")[TeXSmith repository]. Feel free to dive into the source files, front matter, and templates to see exactly how each document is assembled.

These examples also double as test cases for TeXSmith’s continuous integration (CI) pipeline, making sure that improvements to the engine don’t accidentally break existing features.

This collection will continue to grow as we add new examples and templates. Want to contribute? Send us a pull request! Our aim is to build a rich, community-driven library that inspires TeXSmith users and supports a wide variety of needs.
