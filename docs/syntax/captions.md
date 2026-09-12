# Captions

Markdown doesn’t ship with a native caption primitive for figures or tables. The closest thing is image `alt` text:

```md
![This is the alt text](image.png)
```

Alt text exists for accessibility, not for captions. Some browsers show it as a tooltip, but it is not a real caption and you can’t style it separately. Moreover, since it is inserted in an HTML tag's attribute, it can’t contain block elements or complex formatting.

TMark's answer is the **caption line**: a paragraph of its own, adjacent to the
float, spelled `Kind: text {#id}`.

```md
As seen in @fig:results, the results are significant.

![This is the alt text](https://picsum.photos/400/150)

Figure: This is the caption for the figure. {#fig:results}
```

The kinds are `Figure:`, `Table:` and `Listing:`. The attribute list is
optional and is a full one (`{#fig:plot .wide}`); its `#id` is the float's
anchor. Prefixed ids (`fig:`, `tbl:`, `lst:`) are the recommended convention
and are what `@` references read best.

```md {.snippet}
As seen in @fig:results, the results are significant.

![This is the alt text](https://picsum.photos/400/150)

Figure: This is the caption for the figure. {#fig:results}
```

!!! note "The PyMdownX caption block is deprecated"
    `/// caption` and `/// figure-caption` with an indented `attrs:` line are
    still parsed, with a deprecation warning, until `tmark fmt` has had time to
    rewrite the corpus (see [Migrating to TMark](../guide/migration.md)). Their
    id could not contain a colon — `pymdown-extensions` rejected `fig:results`
    and the block silently degraded to plain text — which is exactly the trap a
    canonical spelling must not have. `tmark lint --fix` converts them.

Enable numbering and each document gets its own sequence starting at 1.

## LaTeX

LaTeX wraps figures/tables in `figure`/`table` environments, uses `\caption{}` for the text, and `\label{}` for cross-references:

```latex
As seen in Figure \ref{fig:results}, the results are significant.

\begin{figure}[htbp]
  \centering
  \includegraphics{image.png}
  \caption{This is the caption for the figure.}
  \label{fig:results}
\end{figure}
```

## Addressing issues

1. Consistent numbering across a document
2. Easy cross-references
3. Short captions for lists of figures/tables

### Coherent numbering

Markdown headings aren’t numbered, so figures/tables can’t piggyback on heading numbering. On the web that’s fine—hyperlinks rule the navigation story—but in print numbering is essential. Guideline:

> Printed documents shall have numbered heading elements, figures, and tables for cross-referencing. Web documents, however, should not have numbered headings, figures, or tables, relying instead on hyperlinks for navigation.

Printed LaTeX floats figures and tables, so writers can’t assume a caption stays “above” or “below” the reference. HTML is literal: the figure stays where you put it.

> On printed documents, the words "above" and "below" when referring to figures and tables shall never be used, as their position may vary due to floating. On web documents, "above" and "below" may be used, as figures and tables appear exactly where they are defined.

`tmark lint` flags a position word next to a reference (`position-word`) for
exactly this reason.

### Cross-referencing captions

That rule complicates cross-references: web versions prefer “this figure below,” whereas LaTeX wants “Figure 2.” A *textual* reference lets you write the prose and keeps the number out of the body:

```md
As seen in [this figure](#fig:results), the results are significant.

As seen [here](#fig:results), the results are significant.

The results [shown](#fig:results) are significant.
```

On the web the text is the link and nothing is added. In paged media a
hyperlink is not enough, so the template appends a locator whose shape is
declared per medium:

```yaml
press:
  refs:
    textual:
      print: "{text} ({number})"   # "this figure (3)", or "{text} (p. {page})"
      web: "{text}"
```

When you want the number *in* the prose, refer with the `@` sigil and let the
counter render the label word:

```md
As seen in @fig:results, the results are significant.
```

Language is handled by the counter registry, not by you: “Figure” in English,
“figure” (lowercase) mid-sentence in French, “Abbildung” in German.
`@Fig:results` capitalises the label word at the start of a sentence.

In LaTeX the caption id is emitted verbatim as the `\label`:

```latex
As seen in Figure \ref{fig:results}, the results are significant.
```

The empty-link form `[](#fig:results)` is the class-C fallback for pure-Markdown
toolchains and resolves to the same reference.

### Short caption names

Printed lists of figures appreciate a condensed caption. LaTeX handles this via the optional `\caption[]` argument:

```latex
\caption[Short caption for list of figures]{This is the caption for the figure.}
```

TMark reuses the Markdown `alt` text as that short entry, and the caption line
carries the long one:

```md
![Short caption for the list of figures](image.png)

Figure: This is the caption for the figure, with **Markdown**. {#fig:results}
```

## Caption lines in detail

```md
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Table: This is the caption for the table. {#tbl:sample}
```

````md
```python
def bubble_sort(items): ...
```

Listing: Bubble sort, naive version. {#lst:bubble}
````

A `Listing:` line makes the code block a numbered listing whose caption is the
block's header and whose id is its label, in LaTeX as in Typst.

The canonical **source** position is *after* the block; where the caption is
*printed* (above a table, below a figure) is the template's business. A
`Table:` line placed before the table is accepted for Pandoc compatibility, and
the printer never emits it.

The attachment rule is one rule for every kind: a caption line attaches to the
block *before* it when that block is a float that has no caption yet, otherwise
to the float *after* it. Inside a `::: figure` container a caption with no such
neighbour is the caption of the figure itself. A caption line with no float
next to it stays a plain paragraph and raises `caption-no-host`.

## Subfigures

A `::: figure` container groups images; each becomes a subfigure, and the
caption is a `Figure:` line like everywhere else:

```md
::: figure {cols=2}
![Boot](boot.png){#fig:boot}
![Crash](crash.png){#fig:crash}

Figure: Watchdog traces before and after the fix. {#fig:traces}
:::
```

This renders “Figure 1” with “(a)”, “(b)”; `@fig:crash` yields “figure 1b”.
