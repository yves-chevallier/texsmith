#set document(
title: "Progress Bars",
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
#text(size: 1.8em, weight: "bold")[Progress Bars]]
#v(1.5em)

#ts-callout-style.update("fancy")

The `texsmith.progressbar` extension renders Markdown shorthand into #ts-logo("LaTeX") progress bars:

```
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]{: .candystripe}
[=100% "Launch"]{: .thin}
```

#ts-progress(0.25, label: "Research")
#ts-progress(0.5, label: "Implementation")
#ts-progress(0.75, label: "Review", class: ("candystripe"))
#ts-progress(1, label: "Launch", thin: true)
