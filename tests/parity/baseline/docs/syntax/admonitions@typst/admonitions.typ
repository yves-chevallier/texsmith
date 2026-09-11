#set document(
  title: "Admonitions",
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
  #text(size: 1.8em, weight: "bold")[Admonitions]
]
#v(1.5em)

Admonitions are little callout blocks for surfacing notes, warnings, tips, and whatever else you need to highlight. Python-Markdown’s `admonition` extension powers them.

You can render them in two flavors. The plain/static variant looks like this:

```markdown
!!! note "This is a Note"
    Any number of other indented Markdown elements.

    This is the second paragraph.
```

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
  #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)This is a Note]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Any number of other indented Markdown elements.

    This is the second paragraph.
  ]
]

Prefer collapsible callouts? Use the foldable form:

```markdown
??? note "This is a Note"
    Any number of other indented markdown elements.

    This is the second paragraph.
```

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
  #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)This is a Note]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Any number of other indented markdown elements.

    This is the second paragraph.
  ]
]

= LaTeX Rendering

TeXSmith maps admonitions onto the `tcolorbox` package automatically, so they come through in LaTeX without extra work. Template authors can still restyle them via the preamble or dedicated slots.

Built-in templates like `article` and `book` ship with sensible defaults. Tweak the look by setting `callout_style` in front matter (or via `--attribute callout_style=<style>`):

```yaml
---
press:
  callout_style: classic  # fancy | classic | minimal
---
```

- `fancy` (default): colored headings with icons.
- `classic`: black-and-white layout with a bold left rule.
- `minimal`: subtle border, rounded corners, and no icons.

= Built-in Admonition Types

The following admonition types are built into the `admonition` extension:

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
  #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)Note]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A Note
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00BFA5"), rest: 0.4pt + rgb("#00BFA5")))[
  #block(width: 100%, fill: rgb("#00BFA5").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00BFA5"))[⭐#h(0.4em)Tip]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A Tip
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FFB200"), rest: 0.4pt + rgb("#FFB200")))[
  #block(width: 100%, fill: rgb("#FFB200").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FFB200"))[⚠#h(0.4em)Warning]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A Warning
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#D81B60"), rest: 0.4pt + rgb("#D81B60")))[
  #block(width: 100%, fill: rgb("#D81B60").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#D81B60"))[❗#h(0.4em)Important]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    An important notice
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#C62828"), rest: 0.4pt + rgb("#C62828")))[
  #block(width: 100%, fill: rgb("#C62828").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#C62828"))[🔥#h(0.4em)Danger]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A danger notice
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00B8D4"), rest: 0.4pt + rgb("#00B8D4")))[
  #block(width: 100%, fill: rgb("#00B8D4").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00B8D4"))[ℹ#h(0.4em)Info]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    An info notice
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00BFA5"), rest: 0.4pt + rgb("#00BFA5")))[
  #block(width: 100%, fill: rgb("#00BFA5").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00BFA5"))[💡#h(0.4em)Hint]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A Hint
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#808080"), rest: 0.4pt + rgb("#808080")))[
  #block(width: 100%, fill: rgb("#808080").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#808080"))[🎤#h(0.4em)Seealso]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A see-also notice
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#64DD17"), rest: 0.4pt + rgb("#64DD17")))[
  #block(width: 100%, fill: rgb("#64DD17").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#64DD17"))[❓#h(0.4em)Question]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    A question notice
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00B0FF"), rest: 0.4pt + rgb("#00B0FF")))[
  #block(width: 100%, fill: rgb("#00B0FF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00B0FF"))[📄#h(0.4em)Abstract]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    An abstract
  ]
]
