#set document(
title: "Author",
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
#text(size: 1.8em, weight: "bold")[Author]]
#v(1.5em)

#figure(
image("52489316.jpg", width: 50%),
caption: [Yves Chevallier],
)

I'm Yves Chevallier, the creator and maintainer of TeXSmith. I work full-time as an associate professor at #link("https://www.heig-vd.ch")[HEIG-VD] in Switzerland, where I teach software engineering. My research interests revolve around software architecture, meta-generation, and—naturally—documentation tooling. Before drifting into academia, I trained as an electronics engineer with a focus on real-time embedded systems for motion-control applications.

I originally built TeXSmith mostly for fun—and partly to see how far AI-assisted tooling can be pushed. Judging by the pace of progress, this was probably a terrible idea: my job may well be obsolete in a few years.
