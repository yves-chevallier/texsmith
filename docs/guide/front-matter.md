# YAML Front Matter

Every Markdown document can carry a small block of metadata at the very top, fenced by `---` markers. This is the **front matter**: a YAML island living rent-free above your prose. Static site generators like MkDocs read it to drive per-page configuration, and TeXSmith hooks into the same convention to steer how a document is parsed, typeset, and ultimately rendered to LaTeX or PDF.

A guiding principle: **keep content and form apart**. Templates, font sizes, margins, paper format, and other typographic knobs belong in the front matter; the body should care only about ideas, sentences, and equations. Other tools take a different stance, see [Quarkdown](https://quarkdown.com/), which weaves configuration directly into the document body. Both are valid, but TeXSmith favors the separation, your future self will thank you when swapping templates without touching a single paragraph.

## Press

The `press` block holds everything related to the printed (or PDF'd) artifact, title, authors, template choice, and any template-specific slots:

```yaml
press:
  title: "My Document Title"
  subtitle: "An In-depth Exploration"
  template: article
  authors:
    - name: "Alice Smith"
      affiliation: "University of Examples"
  slots:
    abstract: Abstract
```

!!! note

    The `press` section is optional. Keys like `title` and `authors` may also live at the root of the front matter, and TeXSmith will pick them up just fine. Nesting them under `press` keeps things tidy and avoids stepping on the toes of other static site generators that may want the root-level keys for themselves.

Each template exposes its own set of attributes (cover styles, sidebar toggles, custom slots, …). Head over to the [Template Guide](templates/index.md) for the full menu.

## Bibliography

References can be declared inline, right next to the document that cites them, no external `.bib` file required (though one still works if you prefer). Mix DOI shortcuts with fully-spelled-out entries as needed:

```yaml
bibliography:
  AB2020: doi:10.1000/xyz123
  CD2019:
    type: book
    author: "John Doe"
    title: "Example Book"
    year: "2019"
```

The full syntax, supported entry types, and resolution rules are documented in the [Bibliography Guide](features/bibliography.md).

## Glossary

When the glossary feature is enabled, entries are declared in the front matter and grouped into logical tables. Symbols, acronyms, and domain-specific jargon all coexist peacefully:

```yaml
glossary:
  style: long # or short
  groups: # Grouping in different tables (optional)
    symbols: Mathematical symbols and notations
    corporate: Organizational terms
    technology: Technology-related terms
  entries:
    "$\\phi$":
      group: symbols
      description: Angle in radians
    ONU:
      group: corporate
      description: United Nations Organization
    AI:
      group: technology
      description: Artificial Intelligence
```

See the [Glossary Guide](features/glossary.md) for sorting behavior, cross-references, and styling options.
