# Notes on TeXSmith Extensions

TeXSmith is better to be used with some of its own extensions mostly to add LaTeX-specific missing features in Markdown documents. These extensions are also designed to be compatible with MkDocs and Mkdocs-Material for better in-browser rendering.

mostly uses empty links with custom attributes to add metadata to the HTML output, then process it in the LaTeX generation phase.

- Index entries also used to create tags for Lunr search on MkDocs site.
- Glossary entries to define specific terms used in the documentation.
- Citations to manage references and bibliographies.
- Cross-references to refer to figures, tables, sections, etc.
- Custom LaTeX blocks to insert raw LaTeX code in the generated document.

## Syntax

The chosen syntax follows these rules:

1. Easy to write in Markdown.
2. Compatible with common Markdown parsers.
3. Avoid conflicts with existing Markdown syntax and extensions.
4. Least intrusive in the document content.

### Proposition

`@[]` Smart references
: Replaced with the target identifier depending on the context. Figures and tables are replaced with `Table X` or `Figure Y`, sections with `Section Z`, equations with `(N)`, theorems with `Theorem M`, etc.

`^[]` Footnotes and bibliographic citations
: Replaced with footnote numbers if defined or bibliographic citations depending on the context.

`#[]` Index entries
: Used to create index entries for the document, these entries are invisible in the rendered output HTML but are processed to generate an index in the final LaTeX document or in tags for Lunr search when using MkDocs.




- `[](:)` Add content
- `@()`
- `^[]` `\cite{}` Bibliographic citation
- `#[]`, `\index{}` Index entry

## Other extensions

- Epigraph defined in front matter using `epigraph` key.
- Letterine `:[A](natoly)`
- Wikipedia

## Index

Entries in classic books index can be:

- Normal text
- Italic text (page reference is not the main topic)
- Bold text (main topic of the section)
- Bold italic text (very important topic)
- Nested entries

To create a tag in the index:

```md
Do you know the Gulliver's Travels story about the egg dispute?
#[endianness]{i}

#[endianness]{ib}
#[endianness]{b}
#[byte order][endianness]{i}

```

## Citations

Bibliographic references can be added using two different methods:

1. Use a `.bib` file and cite entries using `^[]` syntax.
2. Use front matter to define references directly with DOIs or manual entries.

```yaml
---
bibliography:
  # Just DOI entry, TeXSmith will fetch the rest
  ein05: https://doi.org/10.1002/andp.19053221004
  # Manual entry
  KOFINAS2025:
    type: article
    title: "The impact of generative AI on academic integrity of authentic assessments within a higher education context"
    authors:
      - name: "Alexander K. Kofinas"
        affiliation: "University of Example"
      - "Crystal Han-Huei Tsay"
      - "David Pike"
    journal: "British Journal of Educational Technology"
    date: 2025-03
    volume: 56
    number: 6
    pages: "2522-2549"
    url: https://doi.org/10.1111/bjet.13585
---
We know that time is relative ^[ein05] and recent work explores
assessment ^[KOFINAS2025]. You can also cite multiple
references ^[ein05,KOFINAS2025].
```

Or with the CLI:

```sh
texsmith article.md article.bib
```

Or directly in Python:

```python
from pathlib import Path

from texsmith.api.service import ConversionRequest, ConversionService

service = ConversionService()
request = ConversionRequest(
    documents=[Path("article.md")],
    bibliography_files=[Path("article.bib")]
)
response = service.execute(request)
tex_path = response.render_result.main_tex_path
print(f"LaTeX written to: {tex_path}")
```

## Math

Inline math can be written using standard Markdown syntax with dollar signs `$...$` or `\(...\)` for inline math and `$$...$$` or `\[...\]` for display math which is usually supported by most Markdown parsers.

However numbered equations are not natively supported in Markdown. TeXSmith provides everything for it.

```md
{#pythagoras}
: $$a^2 + b^2 = c^2$$

From @[pythagoras], we know that...
```

Equation will be rendered as the equation number in parentheses and can be referenced in the text.

## Thorem

We use admonitions to define theorems, lemmas, definitions, etc.

```md
!!! theorem "Pythagorean Theorem" {#thm:pythagoras}
    This is a theorem about right triangles and can be summarised in the next
    equation
    $$ x^2 + y^2 = z^2 $$
```

It will be rendered as:

```latex
\begin{theorem}[Pythagorean theorem]
\label{pythagorean}
This is a theorem about right triangles and can be summarised in the next
equation
\[ x^2 + y^2 = z^2 \]
\end{theorem}
```

TeXSmith automatically generates the foollowing admonition types:

- Thorems (📐)
- Corollary (🧾)
- Lemma (📜)
- Proof (🔍)

## Glossary

Specific terms used in the documentation can be defined in a glossary section.
We must distinguish from :

Glossary entries
: Explanations of specific terms (single or multiple words) used in the documentation.

Acronyms
: Shortened forms of terms or phrases, usually formed from the initial letters of the words such as UNESCO or NASA.

They can be defined in the front matter as follows:

```yaml
acronyms:
  nasa:
    name: NASA
    description: National Aeronautics and Space Administration
  unesco:
    name: UNESCO
    description: United Nations Educational, Scientific and Cultural Organization
glossary:
  solid:
    name: S.O.L.I.D.
    description: |
        Acronym for five design principles intended to make software designs more understandable, flexible, and maintainable.

        1. Single Responsibility Principle
        2. Open/Closed Principle
        3. Liskov Substitution Principle
        4. Interface Segregation Principle
        5. Dependency Inversion Principle
  liskov:
    name: Liskov Substitution Principle
    description: |
        The Liskov Substitution Principle (LSP) states that objects of a superclass should be replaceable with objects of a subclass without affecting the correctness of the program. In other words, if S is a subtype of T, then objects of type T in a program may be replaced with objects of type S without altering any of the desirable properties of that program (e.g., correctness).
```

From the Markdown document, we can reference glossary entries as follows:

```md
From the well known [](gls:solid) principles, the following class must be [](gls:liskov) Substitution Principle compliant.
```

### Wikipedia

Glossary entries can often be found on Wikipedia with which the summary can be automatically fetched.

```md
From the well known [SOLID](https://en.wikipedia.org/wiki/SOLID)
```

With TeXSmith, wikipedia links are automatically converted to glossary entries for the printed document.

```toml
[texsmith.extensions]
wikipedia_glossary = true
```

## Caption

TeXSmith style
: ```md
  A duck image with 25% width
  : ![A duck](duck.jpg){width=25%}

  Table Caption Avec une grosse famille de chats  {#bigcats}
  : | Cat Name    | Age | Color      |
    | ----------- | ---:| ---------- |
    | Whiskers    |  2  | Tabby      |
    | Mittens     |  5  | Black      |
  ```

Pymarkdown style
: ```md
  ![A duck](duck.jpg){width=25%}

  /// figure-caption
      attrs: {#foobar}
      Avec un chocolat violet qui sent la **vanille**
  ///
  ```

## Formatting

In Markdown you can have **bold**, *italic*, and `inline code`. But, with Pymarkdown extensions you can also have ~~strikethrough~~, ==highlighted text==, ^^inserted text^^, {++inserted text++}, {~~deleted text~~}, {==highlighted text==}.

One missing feature is small capitals which can be done using the following syntax: §§Small Capitals§§.

```markdown
§§Small Capitals§§
```

which will be rendered as:

```latex
\textsc{Small Capitals}
```

## Tables

One of the limitations of Markdown is the lack of support for complex table features such as multi-row and multi-column cells, cell alignment, and captions.

When a table is too large to fit on the page several strategies can be used:

- Slightly resize the table to fit the page
- Allow cells to break on multiple lines
- Rotate the table to landscape orientation