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

You can reference another section in the same document or cross-link to other files in the project.

Linking to another file? TeXSmith targets the destination’s main heading and drops a proper hyperlink—handy for navigation-friendly PDFs without any manual tinkering.

```markdown
See the [Code Examples](code.md) for more details.
```

Skip the link text and TeXSmith injects the section number for the print build automatically.
```markdown
See the section [](code.md) for more details.
```

```markdown
## Section Title {#sec:section-title}

Placeholder text that other sections can reference.

## Other Section

Check section @[sec:section-title] for more details.
```

### Autorefs

When the `mkdocs-autorefs` extension is enabled you can use the `[text][label]` syntax to generate automatic references to headings.

## External References

Reference external resources (HTTP/HTTPS) with vanilla Markdown link syntax:

```markdown
For more information, visit the [TeXSmith Website](https://texsmith.org).
You can also check our GitHub repository at https://github.com/yves-chevallier/texsmith.
```

Printed output uses the usual LaTeX link commands:

```latex
For more information, visit the \href{https://texsmith.org}{TeXSmith Website}.
You can also check our GitHub repository at \url{https://github.com/yves-chevallier/texsmith}.
```

## Bibliographic References

Markdown lacks native bibliography support, so TeXSmith reuses the footnote syntax and BibTeX/front matter keys. See the documentation on [Bibliography management](../guide/features/bibliography.md) for more details.

```markdown
---
bibliography:
  einstein1905: https://doi.org/10.1002/andp.19053221004
---
Einstein's theory of relativity revolutionized physics. [^einstein1905]
```

## Footnotes

Use footnotes to park side comments without cluttering the main text. Markdown marks them with superscript numbers; the rendered document moves the details to the bottom of the page or section.

```markdown
This is a sample sentence with a footnote.[^1]

[^1]: This is the footnote text that provides additional information.
```

Footnotes are limited to one line in print—keep them tight.

## Equations

You can include mathematical equations in your document using LaTeX syntax and use `\label{}` to reference them later.

```markdown
\begin{equation}
E = mc^2
\label{eq:einstein}
\end{equation}

As shown in Equation $\eqref{eq:einstein}$, energy is equal to mass times the speed of light squared.
```

For consistency, TeXSmith provides the shorthand `@[label]` to reference it.

```markdown
As shown in Equation @[eq:einstein], energy is equal to mass times the speed of light squared.
```

## Figures

Figures are any diagram with a caption and label for cross-references.

```markdown
!!! figure {#fig:sample-figure}
    ![Sample Figure](image-url.jpg)
```

Reference the figure anywhere using its label.

```markdown
As shown in Figure @[fig:sample-figure], the data illustrates...
```

Both web and print outputs number figures automatically, though the actual numbers may differ because each layout floats content differently.

## Tables

Tables present structured data; give them a label so you can reference them later.

```markdown
!!! table {#tab:sample-table}
    | Header 1 | Header 2 |
    |----------|----------|
    | Cell 1   | Cell 2   |

    This is a sample table for cross-references.

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

Listing @[code:bubble-sort] shows the classic bubble sort.
```

## Tags and Index Entries

Add tags or index entries to associate keywords with specific sections or topics in the document.

```markdown
This section covers advanced sorting algorithms. {index}[algorithm]
```

See the section [Index / Tags][index-tags] for more details on how to manage index entries.

## Naming Conventions

Before hypertext, references revolved around numbers: pages, figures, tables, equations.

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

In French, the reference type stays lowercase unless it begins the sentence.

> Voir le tableau 7 pour plus de détails. La figure 42 illustre le concept.
> Le tout est expliqué à la section 1.

### English

In English we capitalize the reference type and skip the article (“Table 7,” not “the Table 7”).

> See Table 7 for more details. Figure 42 illustrates the concept.
> Everything is explained in Section 1.

### German

German capitalizes the reference type too.

> Siehe Tabelle 7 für weitere Details. Abbildung 42 veranschaulicht das Konzept.
> Alles wird in Abschnitt 1 erklärt.
