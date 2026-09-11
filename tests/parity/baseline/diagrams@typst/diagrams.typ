#set document(
  title: "Diagram Integration",
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
  #text(size: 1.8em, weight: "bold")[Diagram Integration]
  #linebreak()
  #text(size: 1.2em)[An Overview of drawio and mermaid diagram integration]
]
#v(1.5em)

You can embed Draw.io or Mermaid diagrams directly in Markdown. This keeps
technical documentation close to the visuals it describes, and the package
takes care of converting each diagram to an image that the final LaTeX
document can reference automatically.

= Draw.io Diagram

#figure(
  image("<HASH>.png", width: 60%),
  caption: [Euclidean algorithm for the greatest common divisor],
)

= Mermaid Diagram

#figure(
  image("<HASH>.png"),
  caption: [Vegetable harvesting algorithm],
)
