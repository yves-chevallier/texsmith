# Notes on TeXSmith Extensions

TeXSmith extensions mostly uses empty links with custom attributes to add metadata to the HTML output, then process it in the LaTeX generation phase.

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

- `[](:)` Add content
- `@{}` Invisible content
- `@[]`
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

```md
---
bibliography:
  EIN05: https://doi.org/10.1002/andp.19053221004
  KOFINAS2025:
    type: article
    title: "The impact of generative AI on academic integrity of authentic assessments within a higher education context"
    authors:
      - "Alexander K. Kofinas"
      - "Crystal Han-Huei Tsay"
      - "David Pike"
    journal: "British Journal of Educational Technology"
    date: 2025-03
    volume: 56
    number: 6
    pages: "2522-2549"
    doi: 10.1111/bjet.13585
    url: https://doi.org/10.1111/bjet.13585
---
We know that time is relative ^[EIN05] and recent work explores assessment ^[KOFINAS2025].
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

## Glossary

Specific terms used in the documentation can be defined in a glossary section.

```md
---
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
---
From the well known [S.O.L.I.D.](gls:solid) principles, the following class must be [](gls:liskov) Substitution Principle compliant.
```

### Wikipedia

Glossary entries can often be found on Wikipedia with which the summary can be automatically fetched.

```md
From the well known [S.O.L.I.D.](https://en.wikipedia.org/wiki/SOLID)
```

With TeXSmith, wikipedia links are automatically converted to glossary entries for the printed document.

```toml
[texsmith.extensions]
wikipedia_glossary = true
```

## Caption

```md

![A duck](duck.jpg){width=25%}

Figure: A duck image with 25% width


Figure Caption Avec un chocolat violet qui sent la **vanille**  {#foobar}
: ![A duck](duck.jpg){width=25%}

Table Caption Avec une grosse famille de chats  {#bigcats}
: | Cat Name    | Age | Color      |
  | ----------- | ---:| ---------- |
  | Whiskers    |  2  | Tabby      |
  | Mittens     |  5  | Black      |
```
