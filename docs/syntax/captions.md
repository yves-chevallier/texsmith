# Captions

Markdown doesn’t ship with a native caption primitive for figures or tables. The closest thing is image `alt` text:

```md
![This is the alt text](image.png)
```

Alt text exists for accessibility, not for captions. Some browsers show it as a tooltip, but it is not a real caption and you can’t style it separately. Moreover since it is inserted in an HTML tag's attribute, it can’t contain block elements or complex formatting.

Fortunately, `pymdownx.blocks.captions`, which adds proper caption blocks:

```md
As seen in [this figure](#my-figure), the results are significant.

![This is the alt text](https://picsum.photos/400/150)

/// caption #my-figure
This is the caption for the figure.
///
```

Enable numbering and each document gets its own sequence starting at 1.

```md { .snippet }
As seen in [this figure](#my-figure), the results are significant.

![This is the alt text](https://picsum.photos/400/150)

/// caption
    attrs: {id: my-figure}
This is the caption for the figure.
///
```

## LaTeX

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

## Addressing issues

1. Consistent numbering across a document
2. Easy cross-references
3. Short captions for lists of figures/tables

### Coherent numbering

Markdown headings aren’t numbered, so figures/tables can’t piggyback on heading numbering. On the web that’s fine—hyperlinks rule the navigation story—but in print numbering is essential. Guideline:

> Printed documents shall have numbered heading elements, figures and tables for cross-referencing. Web document however should not have numbered headings, figures or tables, relying instead on hyperlinks for navigation.

Printed LaTeX floats figures and tables, so writers can’t assume a caption stays “above” or “below” the reference. HTML is literal: the figure stays where you put it.

> On printed documents, words "above" and "below" when referring to figures and tables shall never be used as their position may vary due to floating. On web documents, "above" and "below" may be used as figures and tables appear exactly where they are defined.

### Cross-referencing captions

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
As seen in [](#fig:my-figure), the results are significant.
```

Any link whose fragment starts with `fig:` is decorated with the assigned number. The HTML output looks like:

```html
As seen in <a href="#fig:my-figure">Figure <span class="caption-number">1</span></a>, the results are significant.
```

In LaTeX:

```latex
As seen in Figure \ref{fig:my-figure}, the results are significant.
```

Or with `cleveref`:

```latex
As seen in \Cref{fig:my-figure}, the results are significant.
```

Pandoc users write `{@fig:my-figure}`; the idea is the same.

### Short Caption Names

Printed lists of figures appreciate a condensed caption. LaTeX handles this via the optional `\caption[]` argument:

```latex
\caption[Short caption for list of figures]{This is the caption for the figure.}
```

TeXSmith reuses the Markdown `alt` text as that short entry:

```md
![Short caption for list of figures](image.png)

/// figure-caption #my-figure
This is the caption for the figure.
///
```

The current syntax is a bit verbose. In the future we’d like a shorthand along these lines:

```md
![Short caption](image.png){#my-figure}

Caption: This is the caption for the figure.

```

## Tables

Tables follow the same pattern:

```md
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Table: This is the caption for the table. {#my-table, short="Short caption for list of tables"}
```
