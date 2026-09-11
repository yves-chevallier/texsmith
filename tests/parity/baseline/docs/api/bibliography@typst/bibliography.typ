#set document(
  title: "Bibliography",
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
  #text(size: 1.8em, weight: "bold")[Bibliography]
]
#v(1.5em)

::: texsmith.core.bibliography

::: texsmith.core.bibliography.collection

::: texsmith.core.bibliography.doi

::: texsmith.core.bibliography.issues

::: texsmith.core.bibliography.parsing
