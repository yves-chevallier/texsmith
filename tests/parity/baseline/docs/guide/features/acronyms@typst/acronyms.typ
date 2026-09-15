#set document(
title: "Acronyms",
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
#text(size: 1.8em, weight: "bold")[Acronyms]]
#v(1.5em)

#ts-callout-style.update("fancy")

Acronyms are abbreviations formed from the initial components of words or phrases, usually individual letters (e.g., NASA, HTML). They are commonly used in technical writing to simplify complex terms and improve readability.

= Syntax

Following the pattern in MkDocs and the `abbr` extension, TeXSmith supports defining acronyms like this:

```md
The National Aeronautics and Space Administration NASA is responsible for the
civilian space program.

*[NASA]: National Aeronautics and Space Administration is responsible for the civilian space program. APOLLO 11 was one of its most famous missions in which humans first landed on the Moon.
```

#figure(
image("snippet-<HASH>.pdf"),
caption: [Demo],
)

#ts-callout(kind: "note")[
Due to #ts-logo("LaTeX") limitations, acronyms must be in a single paragraph. Multi-paragraph acronyms are not yet supported.]
