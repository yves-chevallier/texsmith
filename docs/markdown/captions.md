# Captions

In Markdown there is no built-in way to add captions to figures and tables. The only available built-in mechanism is to use the `alt` text for images:

```md
![This is the alt text](image.png)
```

Alt text is primarily intended for accessibility purposes, and it is not rendered as a caption in the output. It may pop up as a tooltip in some browsers, but this is not a reliable way to provide captions. Moreover, this text is registred as an attribute of the image, not as a separate caption element, so it cannot be styled.

However, with the help of the `pymdownx.blocks.captions` extension, you can easily add captions to your images and tables in a consistent manner.

```md
As seen in [this figure](#my-figure), the results are significant.

![This is the alt text](image.png)

/// figure-caption #my-figure
This is the caption for the figure.
///
```

When numbering is enabled each figure is numbered incrementally per document. That means each document will have its own numbering sequence starting from 1.

## LaTeX

In LaTeX figures and tables are wrapped in `figure` and `table` environments respectively, and captions are added using the `\caption{}` command. A label can be assigned to each caption using the `\label{}` command, which allows for cross-referencing.

```latex
As seen in Figure \ref{fig:my-figure}, the results are significant.

\begin{figure}[htbp]
  \centering
  \includegraphics{image.png}
  \caption{This is the caption for the figure.}
  \label{fig:my-figure}
\end{figure}
```

## Adressing issues

1. Coherent numbering across the document
2. Cross-referencing captions
3. Specifying short caption name for list of figures/tables

### Coherent numbering

In Markdown, none of the sections are numbered, thus figures and tables cannot be numbered automatically from the document structure. In addition, web browsing does not require any numbering, from my own experience, adding section numbering in HTML doesn't make much sense since hyperlinks are the main way to navigate the document. However in a printed document, numbering is essential for clarity and cross-referencing. So let's define this rule:

> Printed documents shall have numbered heading elements, figures and tables for cross-referencing. Web document however should not have numbered headings, figures or tables, relying instead on hyperlinks for navigation.

Another main difference in printed document is that figures and tables are floated elements, meaning they can be placed in different locations from where they are defined in the source document. This is not the case in web documents where figures and tables appear exactly where they are defined.

> On printed documents, words "above" and "below" when referring to figures and tables shall never be used as their position may vary due to floating. On web documents, "above" and "below" may be used as figures and tables appear exactly where they are defined.

### Cross-referencing captions

The above rule creates a challenge for cross referencing because the text used for cross-referencing must be different depending on the output format. In a web document you would write:

```md
As seen in [this figure below](#my-figure), the results are significant.

As seen [here](#my-figure), the results are significant.

The results [shown](#my-figure) are significant.
```

In a latex document you would write instead:

```latex
As seen in Figure \ref{fig:my-figure}, the results are significant.
```

Moreover the label syntax `Figure` is not written the same way depending on the language. In English it is `Figure`, in French it is `figure` if it is not the begining of a sentence, in German it is `Abbildung`, etc. We cannot hardcode this in an extension because it would not be flexible enough to handle different languages.

Fortunately, document wise figure numbering as handled by `pymdownx.blocks.captions` provides a way to assign unique identifiers to each caption. Thus we can create a custom cross-referencing syntax that works for both web and printed documents. For example:

```md
As seen in [](#fig:my-figure), the results are significant.
```

Any links with `fig:` indicated to complete the link with the figure/table/equation number. The above link would be rendered in html as:

```html
As seen in <a href="#fig:my-figure">Figure <span class="caption-number">1</span></a>, the results are significant.
```

And therefore in vanilla LaTeX as:

```latex
As seen in Figure \ref{fig:my-figure}, the results are significant.
```

But in a more modern approach using `cleveref` package, it would be:

```latex
As seen in \Cref{fig:my-figure}, the results are significant.
```

In Pandoc, references are written `{@fig:my-figure}`

### Short Caption Names

In printed document the caption may be long and descriptive, but in the list of figures/tables we want a shorter version. In LaTeX this is done by providing an optional argument to the `\caption[]` command:

```latex
\caption[Short caption for list of figures]{This is the caption for the figure.}
```

Thanks to the `alt` text of images and tables in Markdown, we can use it as the short caption for the list of figures/tables. Thus the syntax would be:

```md
![Short caption for list of figures](image.png)

/// figure-caption #my-figure
This is the caption for the figure.
///
```

The syntax of `pymdownx.blocks.captions` is quite cumbersome. I would prefer something like this:

```md
![Short caption](image.png){#my-figure}

Caption: This is the caption for the figure.

```

## Tables

For tables

```md
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Table: This is the caption for the table. {#my-table, short="Short caption for list of tables"}
```
