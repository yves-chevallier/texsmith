#set document(
  title: "Booby",
  author: ("Yves Chevallier",),
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
  #text(size: 1.8em, weight: "bold")[Booby]
]
#align(center)[
  Yves Chevallier]
#align(center)[November 16, 2025]
#v(1.5em)

= Introduction

Boobies are seabirds in the genus _Sula_, family Sulidae. They are
large, long-winged birds that plunge-dive for fish. The name "booby"
originates from the Spanish word "bobo", meaning "stupid" or "clown",
due to the birds' apparent lack of fear of humans.

#figure(
  image("booby.png", width: 30%),
  caption: [Booby],
)

= Particularities

Boobies have several distinctive features:

- They have brightly colored feet, which they use in mating displays.
- They are known for their spectacular diving ability, plunging into
    the water from great heights to catch fish.
