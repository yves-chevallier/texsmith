#set document(
  title: "Images",
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
  #text(size: 1.8em, weight: "bold")[Images]
]
#v(1.5em)

Images can be included in Markdown using the following syntax:

```md
![Alt text](https://picsum.photos/400/150){width=50%}
```

The width attribute is useful to scale images directly in the Markdown source.

= Draw.io diagrams

A `.drawio` file included as an image is exported to a vector PDF during the
build:

```md
![Euclidean GCD](pgcd.drawio){width=60%}
```

The export is _cropped_ to the drawing by default — the surrounding canvas the
diagram sits on is discarded, so the figure carries no unexpected white margin
and `width=` scales the drawing itself. When the page layout is part of the
diagram (a frame, a title block, deliberate margins, several drawings placed at
fixed positions on the same sheet), ask for the page instead with `crop=false`:

```md
![Site plan](plan.drawio){width=100% crop=false}
```

This is draw.io's _Size: Page Size_ export: the output covers the page(s) the
drawing spans, at the `pageWidth` / `pageHeight` of the diagram, whichever
backend (`playwright`, `local`, `docker`) performs the conversion.

The same diagram can appear both ways in one document; each variant is exported
and stored as its own asset.

To flip the default for a whole document, set `drawio_crop` in the front matter
(or `--attribute press.drawio_crop=false` on the command line); an image
attribute still wins over it:

```yaml
---
press:
  drawio_crop: false
---
```
