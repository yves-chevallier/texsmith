#set document(
  title: "",
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

<cheese>

= Research Paper

This example shows how TeXSmith can be used to write scientific papers with
Markdown source, bibliographies, and figures. It uses the `article` template
package, which provides a standard article layout with support for
citations, cross-references, and floating figures/tables.

The documentation preview uses the default A4 portrait layout. Click the image
to download the PDF.

Here is the source code for this example:

```markdown

```

```bibtex

```

To render the example manually:

```bash
texsmith cheese.md cheese.bib -tarticle --build
```

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#00B8D4"), rest: 0.4pt + rgb("#00B8D4")))[
  #block(width: 100%, fill: rgb("#00B8D4").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#00B8D4"))[ℹ#h(0.4em)Info]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    Naturally, this article isn’t an actual research paper! It’s AI-generated
    content cooked up purely for demo purposes. One reference _is_ real, though—the one
    containing the original figure. I don’t own the rights to that figure; I simply
    redrew it in vector form. All author names and the contents of the other references
    are completely fictional. Any resemblance to real people or publications is
    entirely coincidental… unless the cheese overlords say otherwise.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
  #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)Note]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    I came up with this example because: (1) as a Swiss person, cheese is basically
    part of my operating system, and (2) when I was a student, a friend of mine did
    his PhD on cheese and collected delightfully absurd cheese-related research that
    nobody would imagine studying scientifically.

    I initially thought about an article on how Swiss music—specifically yodeling—might
    influence cheese ripening. But, well… rheology felt slightly more scientifically
    defensible.
  ]
]
