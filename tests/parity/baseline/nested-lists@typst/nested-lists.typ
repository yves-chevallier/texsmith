#set document(
title: "Nested Lists",
author: ("TeXSmith"),
)
#set page(
paper: "a5",
margin: 2cm,
numbering: "1",
)
#set text(font: "New Computer Modern", size: 10pt, lang: "en")
#set par(justify: true)
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => [
#pagebreak(weak: true)
#v(2em)
#text(size: 1.8em, weight: "bold")[#it]
#v(1em)]

#align(center + horizon)[
#text(size: 2.4em, weight: "bold")[Nested Lists]
#v(0.5em)
#text(size: 1.4em)[Six levels deep]
#v(2em)
#text(size: 1.2em)[TeXSmith]#linebreak()]
#pagebreak()

#outline()
#pagebreak()

#ts-callout-style.update("fancy")

= Deep nesting

Markdown nests a list as deeply as its author indents it. #ts-logo("LaTeX") stops at four
levels of `itemize`, four of `enumerate` and six lists of any kind inside one
another, and says `Too deeply nested`. The `texsmith-lists` package the
templates share lifts both limits to nine levels; this page walks to six.

== Bullets

- Level one
- Level two
- Level three
- Level four
- Level five
- Level six

== Numbers

+ Level one
+ Level two
+ Level three
+ Level four
+ Level five
+ Level six

== Mixed

+ An ordered outline
- with a bullet under it
+ and a number under that
- and a bullet again
+ and a fifth level
- and a sixth
