#set document(
title: "Definition Lists",
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
#text(size: 1.8em, weight: "bold")[Definition Lists]]
#v(1.5em)

Definition lists pair a term with one or more definitions. Markdown sticks to a simple pattern:

```markdown
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```

Which renders as:

/ Apple: Pomaceous fruit of plants of the genus Malus in
the family Rosaceae.
/ Orange: The fruit of an evergreen tree of the genus Citrus.

#ts-logo("LaTeX") output:

```latex
\begin{description}
\item[Apple] Pomaceous fruit of plants of the genus Malus in the family Rosaceae.
\item[Orange] The fruit of an evergreen tree of the genus Citrus.
\end{description}
```

#figure(
image("snippet-<HASH>.png"),
)
