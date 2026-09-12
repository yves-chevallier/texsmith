#set document(
title: "Margin Notes",
author: ("TeXSmith"),
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
#text(size: 1.8em, weight: "bold")[Margin Notes]
#linebreak()
#text(size: 1.2em)[The `{aside}[…]` inline extension]]
#align(center)[
TeXSmith]
#v(1.5em)

= Margin Notes

TeXSmith's margin-note extension adds a single inline shorthand to the
unified `{keyword}[content]` family already used by `{index}[term]` and
`{raw latex}(payload)`. The syntax is:

```
{aside side=…}[note text]
```

where `side` is an optional placement — `left`, `right`, `outer` or `inner` —
selecting a margin explicitly. It compiles down to `\marginnote{…}` from the
`marginnote` #ts-logo("LaTeX") package (auto-loaded on first use).

== Default placement

No suffix means the document's default side. In a `oneside` layout that's
the right margin; in a `twoside` layout, the outer margin (so the note
flips automatically between recto and verso pages).

Most readers appreciate a short quip#ts-aside[default note] that sits
beside the paragraph without interrupting the flow. When margin notes are
kept brief and self-contained, they feel like a friendly aside rather than
a distraction.

== Forced side

Force the left margin with `side=left` and the right margin with
`side=right`. Because
the switch is scoped to a #ts-logo("LaTeX") group, subsequent unqualified notes still
follow the document's default placement.

Some diagrams read better when labelled on the left#ts-aside(side: "left")[left-hand
pointer], while running commentary fits the right-hand
margin#ts-aside(side: "right")[right-hand commentary] more naturally. Mixing the two in
close succession is fine — each note is independent.

== Inline formatting

Margin notes pass through the full inline-Markdown parser, so they support
the usual *bold*, _italic_, `inline code`, and #link("https://example.org")[links].

Viscoelastic materials can be approximated as linear#ts-aside[*Hooke's*
law applies at small strain where the stress is _proportional_ to the
strain] under moderate stress, but non-linear effects dominate above the
yield point.

== Longer notes

The package handles multi-sentence notes gracefully. They line-wrap in the
margin and do not disturb the main text's baseline
grid.#ts-aside[Longer notes wrap over several lines and keep flowing down
the margin. Keep them concise so the reader can scan them without losing
the thread of the main text.]

Below, a denser example mixing sides and inline styles:

- Classical mechanics#ts-aside(side: "left")[see Newton, _Principia_, 1687] predates
the calculus of variations.
- Modern formulations rely on Lagrangians#ts-aside[or Hamiltonians for
energy-based analyses] and variational principles.
- Quantum mechanics#ts-aside(side: "right")[introduces non-commuting
observables] follows in the 20th century.

== Inner / Outer

In a `twoside` layout — like this article — `{o}` (outer) and `{i}` (inner)
are MVP aliases of `{r}` and `{l}` respectively. On single-side documents
they behave identically to their counterparts.
