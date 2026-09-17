#set document(
title: "Notes, asides, index and glossary",
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
#text(size: 1.8em, weight: "bold")[Notes, asides, index and glossary]]
#v(1.5em)

#ts-callout-style.update("fancy")

This page collects the constructs that close the #ts-logo("LaTeX")-sized gaps stock Markdown
leaves behind: index entries, asides, citations, theorems, the glossary and the
acronym list. They cooperate with MkDocs and MkDocs Material, and carry enough
structure for the paged writers to finish the job.

- Index entries double as Lunr tags in MkDocs and page references in #ts-logo("LaTeX").
- Glossary entries and acronyms keep terminology consistent.
- Citations and cross-references wire figures, tables, equations and
bibliography entries together.
- Raw fences and roles let you sprinkle precise #ts-logo("TeX") without polluting the web
build.

= Syntax at a glance

The syntax follows a few rules: easy to type, friendly with standard Markdown
parsers, collision-free, and quiet in the raw text.

/ `@key`, `@[key, p. 3]`: Refer. The registry the key belongs to decides what it renders as: a figure
becomes “Figure 3”, a table “Table 4”, a section “Section 2”, a
bibliography key a citation, `@gls:term` a glossary reference.
/ `{index}[term]` / `#[term]`: Define an index entry. Invisible in the flow, a tag in Lunr, an `\index{}`
entry in #ts-logo("LaTeX").
/ `#(prefix:key)` / `{counter}(prefix:key)`: Define _and print_ a numbered item where no host element exists.
/ `{aside}[…]` / `{aside side=left}[…]`: A remark tangential to the flow. The print templates put it in the margin;
a web template may render a sidebar.
/ `[^1]` with a `[^1]: …` definition: A real footnote, CommonMark's own spelling, untouched.

#ts-callout(kind: "note", title: [0.6 spellings])[
`^[key]` / `[^key]` for citations, `{margin}[…]{l}` for asides and
`{index:reg}[…]{b}` for index options are still parsed with a deprecation
warning. `tmark lint –fix` rewrites them; the table is in
Migrating to TMark.]

= Index

Printed indexes convey intent with typography:

- Normal text: the topic is discussed.
- Italic: quick mention only.
- Bold: this section focuses on the topic.
- Nested entries: group related terms.

The canonical spelling is the `index` role. Extra bracket groups nest (three
levels at most); `main=true` marks the main topic (a bold page number);
`registry=` files the entry under a named index, which is created on first use
and printed where the template chooses.

```md
Do you know the Gulliver's Travels tale about the egg dispute? {index}[endianness]

{index}[*endianness*]

{index main=true}[endianness]

{index}[byte order][endianness]

{index registry=physics main=true}[relativity]
```

Emphasis inside the term is content markup, so the italic form is simply
`{index}[*term*]`. The shorthand `#[…]` is the same node:

```md
The device is little-endian. #[endianness]

#[byte order][endianness]
```

= Asides (margin notes)

Drop a short remark out of the flow with the `aside` role. `side=` is a layout
hint of the same standing as `width=` on an image; the default lives in
`press.aside` (right in `oneside`, outer in `twoside`).

#table(
columns: (1fr, 1fr),
align: (left, left),
table.header([`side=`], [Semantics]),
[(none)], [document default],
[`left`], [force the left margin (scoped `\reversemarginpar`)],
[`right`], [force the right margin],
[`outer`], [outer margin],
[`inner`], [inner margin],
)

```md
Hooke's law {aside}[linear only at small strain] holds below the yield point,
but non-linear effects {aside side=left}[see **Prandtl 1921** for the classical
derivation] dominate above it.
```

An aside has *zero width* in the flow: the whitespace on both sides collapses
to one space and disappears before punctuation, so
`Je suis un chien {aside}[remarque].` renders as “Je suis un chien.” with the
note attached to the preceding word.

Longer asides are a container:

```md
::: aside
A **marginal note** attached to the preceding paragraph.
:::
```

Inline Markdown inside the note (`**bold**`, `*italic*`, `` `code` ``,
`[links](…)`) is preserved all the way to #ts-logo("LaTeX"), where the node becomes
`\tsaside[side=left]{…}` from the `ts-typesetting` fragment, over the
`marginnote` package.

== Width

Margin notes never bleed past the page edge. The fragment ships three defensive
layers alongside `\usepackage{marginnote}`:

+ *Geometry-aware clamp.* An `\AtBeginDocument` hook clamps
`\marginparwidth` to whatever horizontal space the document's geometry
actually reserves for the margin — the smaller of the recto outer
margin and, in `twoside` documents, the verso outer margin as well —
minus `\marginparsep` and a 6 mm safety buffer.
+ *Line-breaker tolerance.* `\marginfont` includes `\sloppy`,
`\emergencystretch=1em` and `\hyphenpenalty=50` so a long technical
word, URL or German compound hyphenates (or stretches inter-word
spacing) rather than poking past the margin box edge.
+ *Footnote-size body.* Notes default to `\footnotesize` so multi-word
notes still fit in narrow margins.

That means a `geometry` block like

```yaml
press:
  geometry:
    left: 3cm
    right: 4cm
```

automatically yields notes that fit on both recto and verso pages — no
manual `marginparwidth=…` tweak needed.

== Font size

Because printed margins are narrow, asides default to `\footnotesize` so
multi-word notes fit without overflowing. Override the default from your own
preamble if you want a different treatment:

```latex
\renewcommand*{\marginfont}{\small\itshape}
```

= Citations

Bibliographic references land in two ways:

+ Point TeXSmith at one or more `.bib` files and cite entries with `@key`.
+ Declare references directly in front matter via DOIs or inline metadata.

```md
---
press:
  sources:
    bibliography:
      # Just a DOI: TeXSmith fetches the rest
      ein05: https://doi.org/10.1002/andp.19053221004
      # Manual entry
      KOFINAS2025:
        type: article
        title: |
          The impact of generative AI on academic integrity of authentic
          assessments within a higher education context
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

We know that time is relative @ein05 and recent work explores assessment
@KOFINAS2025. You can also cite several references at once
@[ein05; KOFINAS2025], add a locator @[ein05, p. 33], or suppress the author
@[-ein05].
```

A DOI can be cited in place, without a front-matter entry, through the
predeclared `doi` prefix: `@doi:10.1002/andp.19053221004`.

Or with the CLI:

```sh
texsmith article.md article.bib
```

Or directly in Python:

```python
from pathlib import Path

from texsmith import ConversionRequest, ConversionService

service = ConversionService()
request = ConversionRequest(
    documents=[Path("article.md")],
    bibliography_files=[Path("article.bib")]
)
response = service.execute(request)
tex_path = response.render_result.main_tex_path
print(f"LaTeX written to: {tex_path}")
```

= Math

Inline math is `$…$`; `\(…\)` is accepted as a #ts-logo("LaTeX")-habit compatibility layer.
Display math is `$$…$$`, with `\[…\]` accepted the same way. Skip the space
right after the opening delimiter.

Numbered equations attach an anchor to the display block, Quarto-style:

```md
$$
a^2 + b^2 = c^2
$$ {#eq:pythagoras}

From @eq:pythagoras, we know that…
```

Equations have an anchor but no caption line: print never captions them.

= Theorems

Theorem environments are callout types with a counter. `theorem`, `lemma`,
`corollary`, `proposition`, `definition` and `proof` are predeclared (`proof`
has no counter).

```md
::: theorem {title="Pythagorean theorem" #thm:pythagoras}
This is a theorem about right triangles and can be summarized in the next
equation.

$$ x^2 + y^2 = z^2 $$
:::

@thm:pythagoras is the oldest of them all.
```

It renders as:

```latex
\begin{theorem}[Pythagorean theorem]
\label{thm:pythagoras}
This is a theorem about right triangles and can be summarized in the next
equation.
\[ x^2 + y^2 = z^2 \]
\end{theorem}
```

Declare your own, and say whether it shares a series:

```yaml
press:
  declare:
    admonitions:
      remark: {name: Remark, counter: eq}   # Springer style: shares the equation counter
```

= Glossary

Specific terms live in the glossary; shorthand belongs in the acronym list. Keep
them separate so TeXSmith can decide when to expand, hyperlink, or index each
one.

/ Glossary entries: Definitions for full terms, whether single words or multi-word concepts.
/ Acronyms: Shortened forms such as NASA or UNESCO, often with an expanded description.

Declare both under `press.declare`:

```yaml
press:
  declare:
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
          Acronym for five design principles intended to make software designs
          more understandable, flexible, and maintainable.
      liskov:
        name: Liskov Substitution Principle
        description: |
          Objects of a superclass shall be replaceable with objects of a
          subclass without affecting the correctness of the program.
```

A glossary entry is a referenceable object like any other, so it uses `@` and
the predeclared `gls` prefix:

```md
From the well-known @gls:solid principles, the following class must comply with
@gls:liskov.
```

The 0.6 spelling `[](gls:term)` is still accepted with a deprecation warning.

== Wikipedia

Many glossary-worthy entries live on Wikipedia, and TeXSmith can pull their
summaries automatically. Network access is opt-in:

```md
From the well-known [SOLID](https://en.wikipedia.org/wiki/SOLID) principles…
```

```yaml
press:
  features:
    glossary.wikipedia: true
```

= Other constructs

- *Epigraphs*: tag a blockquote `{.epigraph}`, or set the front-matter
`epigraph: {quote, source}` key. That key is metadata, not a construct: the
`epigraph` pass builds the very same blockquote from it and sets it _under_
the document's opening heading — between that heading and its content, or at
the top of the document when it opens with something else. The opening
heading is the first block that renders something, so a page that names a
target before its title (`[]{#id}` on its own line), or opens with a comment,
keeps the quote under the heading that follows. `quote` and `source` are
plain text, not Markdown.
- *Lead-ins*: `{lead}[Boot sequence.] The device powers…` sets a run-in
heading. A paragraph that opens with a short strong span is promoted to one
automatically while the `paragraph.lead` feature is on.
- *Comments*: `<!– note to self –>`, inline or block. The node survives the
round-trip and is stripped in every backend by default.
