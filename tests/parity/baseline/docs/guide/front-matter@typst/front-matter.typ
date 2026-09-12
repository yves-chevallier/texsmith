#set document(
title: "YAML Front Matter",
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
#text(size: 1.8em, weight: "bold")[YAML Front Matter]]
#v(1.5em)

Every Markdown document can carry a small block of metadata at the very top, fenced by `—` markers. This is the *front matter*: a YAML island living rent-free above your prose. Static site generators like MkDocs read it to drive per-page configuration, and TeXSmith hooks into the same convention to steer how a document is parsed, typeset, and ultimately rendered to #ts-logo("LaTeX") or PDF.

A guiding principle: *keep content and form apart*. Templates, font sizes, margins, paper format, and other typographic knobs belong in the front matter; the body should care only about ideas, sentences, and equations. Other tools take a different stance, see #link("https://quarkdown.com/")[Quarkdown], which weaves configuration directly into the document body. Both are valid, but TeXSmith favors the separation, your future self will thank you when swapping templates without touching a single paragraph.

= The shape of the front matter

Document metadata stays at the *root*, because that is where MkDocs, Pandoc
and editors read it. Everything TeXSmith owns may sit under `press:` — a
namespace, not a category, whose only job is to keep those keys out of a static
site generator's way. When the same key appears in both places, `press` wins.

```yaml
---
title: Firmware Review          # omitted → the first heading is promoted
authors: [{name: Ada Lovelace, affiliation: Analytical Engine}]
date: 2025-03-15                # ISO date | string | "commit"
lang: en-GB                     # hyphenation, quotes, typographic spacing
id: RHE-423                     # document identifier for cross-document references

press:
  template: book                # article | book | letter | a user template
  base_level: chapter           # what a top-level `#` maps to
  callouts:
    style: fancy                # fancy | classic | minimal
  details: expand               # expand | reference
  code: {engine: pygments}
  slots: {abstract: Abstract}

  declare:                      # kinds: what things *are*
    counters: {…}
    admonitions: {…}
    glossary: {…}
    acronyms: {…}

  sources:                      # where references resolve
    bibliography: {…}
    crossrefs: {…}

  features:                     # the switch registry
    figures.exec: true

  diagnostics:                  # how findings are reported
    deprecated: info
---
```

Four groups, and the split is the same one the body follows: `declare` says a
"Solution" callout _exists_, belongs to the group "Solutions" and is referred to
as "See page N"; the form keys (`template`, `callouts`, `code`, …) say it is
blue with a graduation-cap icon. A document is re-skinned by replacing the form
keys alone.

All sections are validated with pydantic: an unknown key fails at parse time,
not in the PDF.

#ts-callout(kind: "note", title: [The 0.6 layout is deprecated])[
Top-level `bibliography:`, `crossrefs:`, `counters:`, `glossary:`,
`acronyms:` and `admonitions:` are still read, with a deprecation warning
naming the replacement. `tmark lint –fix FILE` moves them; the table is in
Migrating to TMark.]

= Moustaches

Any front-matter value is available in the body as `{{ key }}` or
`{{ press.template }}`, resolved after parsing and never inside code spans or
fenced blocks. Moustaches are substitution, not templating: no logic, no loops,
no filters. An unresolved moustache warns and is left in place, visibly.

= Press

The `press` block holds everything related to the printed (or PDF'd) artifact: the template choice, typographic options, and template-specific slots.

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

Each template exposes its own set of attributes (cover styles, sidebar toggles, custom slots, …). Head over to the Template Guide for the full menu.

= Bibliography

References can be declared inline, right next to the document that cites them, no external `.bib` file required (though one still works if you prefer). Mix DOI shortcuts with fully-spelled-out entries as needed:

```yaml
press:
  sources:
    bibliography:
      AB2020: doi:10.1000/xyz123
      CD2019:
        type: book
        author: "John Doe"
        title: "Example Book"
        year: "2019"
```

Cite them with `@AB2020` or `@[CD2019, p. 12]`. The full syntax, supported entry types, and resolution rules are documented in the Bibliography Guide.

= Glossary

When the glossary feature is enabled, entries are declared in the front matter and grouped into logical tables. Symbols, acronyms, and domain-specific jargon all coexist peacefully:

```yaml
press:
  declare:
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

See the Glossary Guide for sorting behavior, cross-references, and styling options.

= Counters

Document-specific numbered series — findings, requirements, bugs, test cases —
are declared under `press.declare.counters`. Each key is the prefix used by the
`#(…)` markers and the `@…` references in the body:

```yaml
press:
  declare:
    counters:
      n:
        name: Requirement # human-readable name, used in diagnostics
        format: "N-{n:02d}" # optional, defaults to "{n}"
        start: 1 # optional, defaults to 1
      fw:
        name: Firmware finding
        format: "FW-{n:02d}"
```

The predeclared prefixes (`sec`, `fig`, `tbl`, `lst`, `eq`, `thm`, `note`,
`gls`, `doi`) are entries of the same registry, and their fields can be
overridden the same way (`fig: {scope: document}`).

See Custom counters for the marker syntax, the
numbering scope and the backend mapping.

= Cross-document references

`id` gives the document a free identifier (a contract or report number);
`press.sources.crossrefs` declares the inventories published by the documents it
cites:

```yaml
id: RHE-424
press:
  sources:
    crossrefs:
      fwrev: build/firmware-review.refs.json
```

A citation then reads `@fwrev:fw:pas-de-temps` and renders as
`RHE-423-FW-10 p. 14`. See Cross-document references.

= Features

Every switchable behaviour has a dotted name and a default. `press.features`
flips entries, and nothing else in the front matter does.

```yaml
press:
  features:
    figures.exec: true        # execute `python image` fences
    glossary.wikipedia: true  # fetch glossary summaries from Wikipedia links
    paragraph.lead: false     # stop promoting a leading strong span
    strict: true              # never build a PDF from a document with a finding
```

`strict` is the front-matter twin of `–strict`: the build stops with exit
status 1 when any warning or error was recorded, after the `.tex` is written
and before the engine runs. Either spelling turns it on; there is no way to
turn it back off from the command line.

= Diagnostics

`press.features` is a boolean map, so the one three-valued knob lives beside it
rather than inside it:

```yaml
press:
  diagnostics:
    deprecated: info          # warning (default) | info | off
```

It sets the level the parser's two transition codes — `deprecated` and
`deprecated-frontmatter-key` — are reported at, so a document still written in
the 0.6 spellings does not fail its own `strict: true`. `–deprecated` on the
command line wins over it. See #link("diagnostics.md#-deprecated")[Diagnostics].
