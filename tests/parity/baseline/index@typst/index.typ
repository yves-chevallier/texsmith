#set document(
title: "Index Example",
)
#set page(
paper: "a6",
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
#text(size: 1.8em, weight: "bold")[Index Example]]
#v(1.5em)

This document demonstrates the index generation with TeXSmith. You can nest, format and create multiple index entries for terms.

= Granny Smith

A tart apple variety often used in baking and cooking. Known for its bright green skin and crisp texture.
#ts-index([Granny Smith])#ts-index([apple])

= Fuji

A sweet and juicy apple variety that originated in Japan. It has a dense flesh and a balanced flavor.

#ts-index([Fuji])#ts-index([apple])#ts-index([_juicy_])

= Honeycrisp

A popular apple variety known for its crisp texture and sweet-tart flavor. It has a distinctive red and yellow skin.

#ts-index([Honeycrisp])#ts-index([apple])
