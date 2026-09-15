#set document(
title: "Mermaid Diagrams",
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
#text(size: 1.8em, weight: "bold")[Mermaid Diagrams]]
#v(1.5em)

#ts-callout-style.update("fancy")

= Inline diagram

#figure(
image("<HASH>.pdf"),
)

= External file

#figure(
image("<HASH>.pdf"),
caption: [Build pipeline],
)

= Pako URL

#figure(
image("<HASH>.pdf"),
caption: [Example Pako],
)
