#set document(
title: "Plumbing",
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
#text(size: 1.8em, weight: "bold")[Plumbing]]
#v(1.5em)

#ts-callout-style.update("fancy")

This section dives into the inner workings of TeXSmith, exploring its architecture, core components, and the mechanisms that enable its seamless integration of Markdown and #ts-logo("LaTeX"). Whether you're curious about how TeXSmith processes documents or interested in extending its capabilities, this guide offers a concise overview of the plumbing that powers TeXSmith.
