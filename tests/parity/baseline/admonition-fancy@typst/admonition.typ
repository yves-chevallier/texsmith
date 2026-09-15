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
#text(size: 1.2em)[An Overview of *fancy* framed elements]]
#v(1.5em)

#ts-callout-style.update("fancy")

#ts-callout(kind: "note")[
Highlights extra information that’s useful but not critical, helping readers understand nuances.]

#ts-callout(kind: "tip")[
Offers a practical hint that makes the task easier, saving the reader time or effort.]

#ts-callout(kind: "warning")[
Draws attention to something that could cause problems if ignored, helping avoid mistakes.]

#ts-callout(kind: "caution")[
Signals a potentially risky action, encouraging the reader to proceed carefully.]

#ts-callout(kind: "important")[
Emphasizes key information the reader must not overlook to ensure proper understanding.]

#ts-callout(kind: "danger")[
Flags a serious hazard that could break things or cause real harm if mishandled.]

#ts-callout(kind: "info")[
Provides neutral, factual context that supports understanding without urgency.]

#ts-callout(kind: "hint")[
Gives a gentle clue that helps the reader figure something out without revealing everything.]

#ts-callout(kind: "seealso")[
Points to related material so the reader can explore deeper or connected topics.]

#ts-callout(kind: "question")[
Raises an inquiry that prompts reflection or introduces a point the reader should consider.]

#ts-callout(kind: "abstract")[
Summarizes the core ideas to help the reader grasp the purpose of a section or document quickly.]

#ts-callout(kind: "summary")[
Recaps key points so the reader can retain the most important information at a glance.]

#ts-callout(kind: "success")[
Celebrates a positive outcome or achievement, reinforcing good practices and results.]

#ts-callout(kind: "failure")[
Highlights a setback or error, helping the reader learn from mistakes and avoid them in the future]

#ts-callout(kind: "bug")[
Identifies a known issue or problem, guiding the reader on what to watch out for.]

#ts-callout(kind: "quote")[
Presents a relevant quotation that adds authority or perspective to the content.]

#heading(level: 1, numbering: none, outlined: false)[Custom Admonition]

#ts-callout(kind: "unicorn")[
A custom admonition with a unicorn theme, adding a whimsical touch to the information presented.]
