#set document(
  title: "Captions",
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
  #text(size: 1.8em, weight: "bold")[Captions]
]
#v(1.5em)

Markdown doesn’t ship with a native caption primitive for figures or tables. The closest thing is image `alt` text:

```md
![This is the alt text](image.png)
```

Alt text exists for accessibility, not for captions. Some browsers show it as a tooltip, but it is not a real caption and you can’t style it separately. Moreover, since it is inserted in an HTML tag's attribute, it can’t contain block elements or complex formatting.

Fortunately, `pymdownx.blocks.captions` adds proper caption blocks:

```md
As seen in [this figure](#my-figure), the results are significant.

![This is the alt text](https://picsum.photos/400/150)

    attrs: {id: my-figure}
This is the caption for the figure.
```

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FFB200"), rest: 0.4pt + rgb("#FFB200")))[
  #block(width: 100%, fill: rgb("#FFB200").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FFB200"))[⚠#h(0.4em)Identifier restrictions]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    The `id` is declared through the block's YAML options and may not contain
    a colon: `pymdown-extensions` rejects identifiers such as
    `fig:my-figure`, and the whole block then silently degrades to plain
    text (TeXSmith emits a warning when it detects this). The shorthand
    header form `/// caption #my-figure` is likewise not supported by
    `pymdown-extensions` — always use the `attrs:` option shown above.
  ]
]

Enable numbering and each document gets its own sequence starting at 1.

= LaTeX

LaTeX wraps figures/tables in `figure`/`table` environments, uses `\caption{}` for the text, and `\label{}` for cross-references:

```latex
As seen in Figure \ref{fig:my-figure}, the results are significant.

\begin{figure}[htbp]
  \centering
  \includegraphics{image.png}
  \caption{This is the caption for the figure.}
  \label{fig:my-figure}
\end{figure}
```

= Addressing issues

+ Consistent numbering across a document
+ Easy cross-references
+ Short captions for lists of figures/tables

== Coherent numbering

Markdown headings aren’t numbered, so figures/tables can’t piggyback on heading numbering. On the web that’s fine—hyperlinks rule the navigation story—but in print numbering is essential. Guideline:

#quote(block: true)[
  Printed documents shall have numbered heading elements, figures, and tables for cross-referencing. Web documents, however, should not have numbered headings, figures, or tables, relying instead on hyperlinks for navigation.
]

Printed LaTeX floats figures and tables, so writers can’t assume a caption stays “above” or “below” the reference. HTML is literal: the figure stays where you put it.

#quote(block: true)[
  On printed documents, the words "above" and "below" when referring to figures and tables shall never be used, as their position may vary due to floating. On web documents, "above" and "below" may be used, as figures and tables appear exactly where they are defined.
]

== Cross-referencing captions

That rule complicates cross-references: web versions prefer “this figure below,” whereas LaTeX wants “Figure 2.” Examples:

```md
As seen in [this figure below](#my-figure), the results are significant.

As seen [here](#my-figure), the results are significant.

The results [shown](#my-figure) are significant.
```

In LaTeX you’d use:

```latex
As seen in Figure \ref{fig:my-figure}, the results are significant.
```

Language adds another wrinkle: “Figure” in English, “figure” (lowercase) in French mid-sentence, “Abbildung” in German, and so on. Hardcoding wording would be brittle.

Fortunately `pymdownx.blocks.captions` tracks IDs, so TeXSmith can bridge both worlds with a shared syntax:

```md
As seen in [](#my-figure), the results are significant.
```

An empty-text link to a caption id is decorated with the assigned number. The HTML output looks like:

```html
As seen in <a href="#my-figure">Figure <span class="caption-number">1</span></a>, the results are significant.
```

In LaTeX (the caption id is emitted verbatim as the `\label`):

```latex
As seen in Figure \ref{my-figure}, the results are significant.
```

Or with `cleveref`:

```latex
As seen in \Cref{my-figure}, the results are significant.
```

Pandoc users write `{@fig:my-figure}`; the idea is the same.

== Short caption names

Printed lists of figures appreciate a condensed caption. LaTeX handles this via the optional `\caption[]` argument:

```latex
\caption[Short caption for list of figures]{This is the caption for the figure.}
```

TeXSmith reuses the Markdown `alt` text as that short entry:

```md
![Short caption for list of figures](image.png)

    attrs: {id: my-figure}
This is the caption for the figure.
```

= Caption lines

The block form is verbose, and its id may not contain a colon. The caption
_line_ is the shorthand: the paragraph right after the float, spelled
`Kind: text {#id}`, with `Figure:`, `Table:` or `Listing:` as the kind. This
is TMark's canonical spelling, and the one `tmark fmt` prints.

```md
![Short caption for the list of figures](image.png){width=70%}

Figure: This is the caption for the figure. {#fig:my-figure}
```

```md
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Table: This is the caption for the table. {#tbl:my-table}
```

````md
```python
def bubble_sort(items): ...
```

Listing: Bubble sort, naive version. {#lst:bubble}
````

The attribute list is optional and may be a full one (`{#fig:plot .wide}`);
its `#id` is the float's anchor, and ids with a prefix (`fig:`, `tbl:`,
`lst:`) are fine here. The image `alt` stays the short caption. A `Figure:`
line renders exactly like the `/// caption` block above; a `Listing:` line
makes the code block a numbered listing whose caption is the block's title
and whose id is its label, in LaTeX as in Typst.

The line attaches to the float _before_ it when that float is of the matching
kind and has no caption yet, otherwise to the float _after_ it — so the
`Table:` line before its table keeps working. A `Figure:` line under a table,
or a caption line with no float next to it, is left as a plain paragraph.

= Tables

Tables follow the same pattern:

```md
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Table: This is the caption for the table. {#my-table}
```
