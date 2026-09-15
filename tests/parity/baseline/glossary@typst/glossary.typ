#set document(
title: "Structured glossary demo",
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
#text(size: 1.8em, weight: "bold")[Structured glossary demo]]
#v(1.5em)

#outline()
#v(1em)

#ts-callout-style.update("fancy")

= Introduction

This document showcases TeXSmith's structured glossary support. Definitions
live in the YAML front matter: each entry has a description and may be attached
to a group. TeXSmith renders, in declaration order, one table per group plus a
default table for entries that were left ungrouped.

= Technical acronyms

A REST #ts-acr("API") exchanges #ts-acr("JSON") messages over #ts-acr("HTTP"). The first occurrence of every
acronym — #ts-acr("API"), #ts-acr("HTTP"), #ts-acr("JSON") — is automatically replaced with `\acrshort{...}`,
without writing any `\gls{...}` by hand.

= Institutional acronyms

The #ts-acr("UN") coordinates international relief efforts; the #ts-acr("WHO") publishes its health
recommendations.

= Ungrouped acronym

A #ts-acr("DOI") uniquely identifies a scientific publication. With no group attached, it
is listed in the default acronym table.

= Mixing with the legacy syntax

The classic Markdown `*[KEY]: ...` syntax keeps working and merges with the
front-matter definitions.

#ts-acr("NMR") remains a cornerstone of modern molecular analysis.

#v(1em)
#heading(numbering: none)[Acronyms]

/ API: Application Programming Interface
/ DOI: Digital Object Identifier
/ HTTP: HyperText Transfer Protocol
/ JSON: JavaScript Object Notation
/ NMR: Nuclear Magnetic Resonance
/ UN: United Nations
/ WHO: World Health Organization
