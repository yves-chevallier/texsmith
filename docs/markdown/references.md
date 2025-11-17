# References

We define several types of references that can be used throughout the documentation:

Internal References
: These are links that point to other sections within the same document or to other documents within the same project.

External References
: These are links that point to resources outside of the current project, such as websites or external documents.

Bibliographic References
: These are citations that refer to external publications, articles, or books. They are often formatted using a specific citation style (e.g., APA, MLA) and may include a bibliography section at the end of the document.

Footnotes
: Footnotes provide additional information or citations without cluttering the main text. They are typically indicated by a superscript number in the text, with the corresponding footnote text provided at the bottom of the page or section.

Equations
: Mathematical equations can be included in the document using LaTeX syntax. Equations can be labeled and referenced throughout the text.

Tables
: Tables are used to present data in a structured format with rows and columns. They can be labeled and referenced within the document.

Figures
: Figures are images, charts, or diagrams included in the document. They can be labeled and referenced throughout the text.

Listings/Code Blocks
: Code blocks are used to display code snippets in various programming languages. They can be labeled and referenced within the document.

Tags/Index
: Tags or index entries allows to associate keywords with specific sections or topics in the document, making it easier to locate related information.

## Internal References

You can refer to another section within the same document, another document in the same project or simply another file in the same project.

Refer to another file. TeXSmith will hook it to the main heading and insert an hyperlink, useful for navigables PDFs.

```markdown
See the [Code Examples](code.md) for more details.
```

When text is not provided, TeXSmith will use the section number in printed document
```markdown
See the section [](code.md) for more details.
```

```markdown
## Section Title {#sec:section-title}

Blah blah...

## Other Section

Check section @[sec:section-title] for more details.
```

### Autorefs

With `mkdocs-autorefs` extension enabled, you can use the `[text][label]` syntax to create automatic reference to headings.

## External References

You can refer to an external resource (http/https) using standard markdown link syntax.

```markdown
For more information, visit the [TeXSmith Website](https://texsmith.org).
You can also check our GitHub repository at https://github.com/yves-chevallier/texsmith.
```

This will be rendered as a clickable link:

```latex
For more information, visit the \href{https://texsmith.org}{TeXSmith Website}.
You can also check our GitHub repository at \url{https://github.com/yves-chevallier/texsmith}.
```

## Bibliographic References

Bibliography is not supported natively in markdown, TeXSmith uses the footnote syntax to insert bibliographic references based
on a keyword defined in a BibTeX file or in your front-matter. See the documentation on [Bibliography management](../guide/40-bibliography.md) for more details.

```markdown
---
bibliography:
  einstein1905: https://doi.org/10.1002/andp.19053221004
---
Einstein's theory of relativity revolutionized physics. [^einstein1905]
```

## Footnotes

You can add footnotes to provide additional information or citations without cluttering the main text. Footnotes are indicated by a superscript number in the text, with the corresponding footnote text provided at the bottom of the page or section.

```markdown
This is a sample sentence with a footnote.[^1]

[^1]: This is the footnote text that provides additional information.
```

Footnotes are limited to one line in print, so keep them concise.

## Equations

You can include mathematical equations in your document using LaTeX syntax and use `\label{}` to reference them later.

```markdown
\begin{equation}
E = mc^2
\label{eq:einstein}
\end{equation}

As shown in Equation $\eref{eq:einstein}$, energy is equal to mass times the speed of light squared.
```

For sake of consistency, TeXSmith provides the shorthand `@[label]` to reference it.

```markdown
As shown in Equation @[eq:einstein], energy is equal to mass times the speed of light squared.
```

## Figures

Figures are images, charts, or diagrams included in the document identified with a caption and a label for referencing.

```markdown
!!! figure {#fig:sample-figure}
    ![Sample Figure](image-url.jpg)
```

You can reference the figure in your text using its label.

```markdown
As shown in Figure @[fig:sample-figure], the data illustrates...
```

Figures in both web and print outputs will be numbered automatically. However the numbers may differ between outputs due to layout differences.

## Tables

Tables are used to present data in a structured format with rows and columns. You can create tables using markdown syntax and assign a label for referencing.

```markdown
!!! table {#tab:sample-table}
    | Header 1 | Header 2 |
    |----------|----------|
    | Cell 1   | Cell 2   |

    This is a sample table.

Check Table @[tab:sample-table] for more details.
```

## Code Block References

You can reference specific code blocks within your document by assigning them a label.

```markdown
!!! listing {#code:bubble-sort}
    ```python {#code:bubble-sort}
    def bubble_sort(items):
        for i in range(len(items)):
            for j in range(0, len(items)-i-1):
                if items[j] > items[j+1]:
                    items[j], items[j+1] = items[j+1], items[j]
    ```

    Caption for the bubble sort code block.

The bubble sort algorithm defined in Listing @[code:bubble-sort] is a simple sorting algorithm.
```

## Tags and Index Entries

You can add tags or index entries to associate keywords with specific sections or topics in the document.

```markdown
This section covers advanced sorting algorithms. #[algorithm]
```

See the section [][index] for more details on how to manage index entries.

## Naming Conventions

Before computers, references were essentially managed by numbers: page numbers, figure numbers, table numbers, equation numbers, etc.

```text
1. Section

  Some Text

  Table 7: An example table
         +-------+
         | Table |
         +-------+

         +--------+
         | Figure |
         +--------+
  Figure 42: An example figure

2. Another Section

  See Table 7 for more details. The Figure 42 illustrates the concept.
  Everything is explained in Section 1.
```

### French

In French documents, the naming conventions is to write in lowercase the type of reference unless it starts a sentence.

> Voir le tableau 7 pour plus de détails. La figure 42 illustre le concept.
> Le tout est expliqué à la section 1.

### English

In English however, the naming convention is to capitalize the type of reference. We do not use articles before the type of reference.

> See Table 7 for more details. Figure 42 illustrates the concept.
> Everything is explained in Section 1.

### German

In German documents, the naming convention is to capitalize the type of reference as well.

> Siehe Tabelle 7 für weitere Details. Abbildung 42 veranschaulicht das Konzept.
> Alles wird in Abschnitt 1 erklärt.