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
  #text(size: 1.8em, weight: "bold")[Progress Bars]
]
#v(1.5em)

The `texsmith.progressbar` extension renders Markdown shorthand into LaTeX progress bars:

```
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]{: .candystripe}
[=100% "Launch"]{: .thin}
```

#box(width: 9cm, height: 12pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 25%, height: 100%, fill: luma(40%))[]] Research

#box(width: 9cm, height: 12pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 50%, height: 100%, fill: luma(40%))[]] Implementation

#box(width: 9cm, height: 12pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 75%, height: 100%, fill: luma(40%))[]] Review

#box(width: 9cm, height: 6pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 100%, height: 100%, fill: luma(40%))[]] Launch
