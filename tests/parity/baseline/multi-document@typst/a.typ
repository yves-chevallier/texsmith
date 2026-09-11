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

= Zeus

In Greek mythology, Zeus is the king of the gods, ruler of Mount Olympus, and god of the sky, lightning, thunder, law, order, and justice. As the chief deity in the Greek pantheon, Zeus holds a position of supreme authority and power among the gods and mortals alike.
