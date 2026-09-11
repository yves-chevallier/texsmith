#set document(
  title: "Admonitions / Callouts",
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
#set page(columns: 2)
#set heading(numbering: "1.1")

#align(center)[
  #text(size: 1.8em, weight: "bold")[Admonitions / Callouts]
  #linebreak()
  #text(size: 1.2em)[An Overview of **fancy** framed elements]
]
#v(1.5em)

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
  #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)Note]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Highlights extra information that’s useful but not critical, helping readers understand nuances.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00BFA5"), rest: 0.4pt + rgb("#00BFA5")))[
  #block(width: 100%, fill: rgb("#00BFA5").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00BFA5"))[⭐#h(0.4em)Tip]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Offers a practical hint that makes the task easier, saving the reader time or effort.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FFB200"), rest: 0.4pt + rgb("#FFB200")))[
  #block(width: 100%, fill: rgb("#FFB200").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FFB200"))[⚠#h(0.4em)Warning]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Draws attention to something that could cause problems if ignored, helping avoid mistakes.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FF9100"), rest: 0.4pt + rgb("#FF9100")))[
  #block(width: 100%, fill: rgb("#FF9100").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FF9100"))[🚧#h(0.4em)Caution]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Signals a potentially risky action, encouraging the reader to proceed carefully.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#D81B60"), rest: 0.4pt + rgb("#D81B60")))[
  #block(width: 100%, fill: rgb("#D81B60").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#D81B60"))[❗#h(0.4em)Important]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Emphasizes key information the reader must not overlook to ensure proper understanding.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#C62828"), rest: 0.4pt + rgb("#C62828")))[
  #block(width: 100%, fill: rgb("#C62828").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#C62828"))[🔥#h(0.4em)Danger]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Flags a serious hazard that could break things or cause real harm if mishandled.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00B8D4"), rest: 0.4pt + rgb("#00B8D4")))[
  #block(width: 100%, fill: rgb("#00B8D4").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00B8D4"))[ℹ#h(0.4em)Info]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Provides neutral, factual context that supports understanding without urgency.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00BFA5"), rest: 0.4pt + rgb("#00BFA5")))[
  #block(width: 100%, fill: rgb("#00BFA5").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00BFA5"))[💡#h(0.4em)Hint]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Gives a gentle clue that helps the reader figure something out without revealing everything.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#808080"), rest: 0.4pt + rgb("#808080")))[
  #block(width: 100%, fill: rgb("#808080").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#808080"))[🎤#h(0.4em)Seealso]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Points to related material so the reader can explore deeper or connected topics.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#64DD17"), rest: 0.4pt + rgb("#64DD17")))[
  #block(width: 100%, fill: rgb("#64DD17").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#64DD17"))[❓#h(0.4em)Question]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Raises an inquiry that prompts reflection or introduces a point the reader should consider.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00B0FF"), rest: 0.4pt + rgb("#00B0FF")))[
  #block(width: 100%, fill: rgb("#00B0FF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00B0FF"))[📄#h(0.4em)Abstract]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Summarizes the core ideas to help the reader grasp the purpose of a section or document quickly.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00B8D4"), rest: 0.4pt + rgb("#00B8D4")))[
  #block(width: 100%, fill: rgb("#00B8D4").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00B8D4"))[📋#h(0.4em)Summary]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Recaps key points so the reader can retain the most important information at a glance.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00C853"), rest: 0.4pt + rgb("#00C853")))[
  #block(width: 100%, fill: rgb("#00C853").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00C853"))[✅#h(0.4em)Success]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Celebrates a positive outcome or achievement, reinforcing good practices and results.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FF5252"), rest: 0.4pt + rgb("#FF5252")))[
  #block(width: 100%, fill: rgb("#FF5252").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FF5252"))[❗#h(0.4em)Failure]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Highlights a setback or error, helping the reader learn from mistakes and avoid them in the future
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#F50057"), rest: 0.4pt + rgb("#F50057")))[
  #block(width: 100%, fill: rgb("#F50057").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#F50057"))[🐞#h(0.4em)Bug]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Identifies a known issue or problem, guiding the reader on what to watch out for.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#9E9E9E"), rest: 0.4pt + rgb("#9E9E9E")))[
  #block(width: 100%, fill: rgb("#9E9E9E").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#9E9E9E"))[✒️#h(0.4em)Quote]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Presents a relevant quotation that adds authority or perspective to the content.
  ]
]

= Custom Admonition

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FF00FF"), rest: 0.4pt + rgb("#FF00FF")))[
  #block(width: 100%, fill: rgb("#FF00FF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FF00FF"))[🦄#h(0.4em)Unicorn]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A custom admonition with a unicorn theme, adding a whimsical touch to the information presented.
  ]
]
