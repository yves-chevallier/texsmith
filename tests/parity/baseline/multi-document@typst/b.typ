#set document(
  title: "Greek Mythology",
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
  #text(size: 1.8em, weight: "bold")[Greek Mythology]
  #linebreak()
  #text(size: 1.2em)[Gods and Goddesses]
]
#v(1.5em)

= Hera

Hera is the queen of the gods in Greek mythology, known as the goddess of marriage, women, childbirth, and family. She is the wife and sister of Zeus and is often depicted as a majestic and solemn figure, symbolizing the ideal of womanhood and the protector of marriage and the home.
