#set document(
title: "Glossary",
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
#text(size: 1.8em, weight: "bold")[Glossary]]
#v(1.5em)

#ts-callout-style.update("fancy")

In online documentation, a glossary doesn't make much sense because you can
search for terms directly and you have hyperlinks. However, in printed documents, a
glossary can be very useful to provide definitions of terms used in the text.

TeXSmith supports glossaries through the `ts-glossary` fragment: declare the
entries in the front matter under `press.declare.glossary` (and the acronyms
under `press.declare.acronyms`, or inline with `*[KEY]: …`), and the fragment
loads `glossaries`, declares every entry and prints the backmatter.

Nothing has to be enabled by hand. The fragment is activated by the writer,
which names it in `Requires.fragments` as soon as a body emits `\tsgls` or
`\tsacr` — that is, as soon as the document actually uses a glossary term or an
acronym. A document that declares none carries no `ts-glossary.sty`.

`\tsgls{key}` is `\gls` (the first use expands, later ones use the short form);
`\tsacr{key}` is `\acrshort`, the short form wherever it stands.

The declaration syntax, the groups and the sorting rules are in
#link("../front-matter.md#glossary")[YAML Front Matter].
