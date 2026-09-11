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
  #text(size: 1.2em)[An Overview of **classic** framed elements]
]
#v(1.5em)

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[📝#h(0.4em)Note]

  Highlights extra information that’s useful but not critical, helping readers understand nuances.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[⭐#h(0.4em)Tip]

  Offers a practical hint that makes the task easier, saving the reader time or effort.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[⚠#h(0.4em)Warning]

  Draws attention to something that could cause problems if ignored, helping avoid mistakes.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[🚧#h(0.4em)Caution]

  Signals a potentially risky action, encouraging the reader to proceed carefully.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[❗#h(0.4em)Important]

  Emphasizes key information the reader must not overlook to ensure proper understanding.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[🔥#h(0.4em)Danger]

  Flags a serious hazard that could break things or cause real harm if mishandled.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[ℹ#h(0.4em)Info]

  Provides neutral, factual context that supports understanding without urgency.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[💡#h(0.4em)Hint]

  Gives a gentle clue that helps the reader figure something out without revealing everything.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[🎤#h(0.4em)Seealso]

  Points to related material so the reader can explore deeper or connected topics.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[❓#h(0.4em)Question]

  Raises an inquiry that prompts reflection or introduces a point the reader should consider.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[📄#h(0.4em)Abstract]

  Summarizes the core ideas to help the reader grasp the purpose of a section or document quickly.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[📋#h(0.4em)Summary]

  Recaps key points so the reader can retain the most important information at a glance.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[✅#h(0.4em)Success]

  Celebrates a positive outcome or achievement, reinforcing good practices and results.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[❗#h(0.4em)Failure]

  Highlights a setback or error, helping the reader learn from mistakes and avoid them in the future
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[🐞#h(0.4em)Bug]

  Identifies a known issue or problem, guiding the reader on what to watch out for.
]

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[✒️#h(0.4em)Quote]

  Presents a relevant quotation that adds authority or perspective to the content.
]

= Custom Admonition

#block(width: 100%, inset: (left: 10pt, rest: 6pt), stroke: (left: 1.2pt + luma(40%)))[
  #text(weight: "bold")[🦄#h(0.4em)Unicorn]

  A custom admonition with a unicorn theme, adding a whimsical touch to the information presented.
]
