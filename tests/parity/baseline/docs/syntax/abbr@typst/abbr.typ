#set document(
title: "Abbreviations / Acronyms",
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
#text(size: 1.8em, weight: "bold")[Abbreviations / Acronyms]]
#v(1.5em)

Abbreviations are a lightweight mechanism to define acronyms and their
expansions. The spelling is PHP-Markdown-Extra's `abbr`, which every MkDocs site
renders; in #ts-logo("LaTeX") they go through the `glossaries` package, which provides a
rich set of commands for formatting and indexing.

```md
The HTML specification is maintained by the W3C.

*[HTML]: HyperText Markup Language
*[W3C]: World Wide Web Consortium
```

TeXSmith renders that snippet as:

```
$ texsmith abbr.md
The \acrshort{HTML} specification is maintained by the \acrshort{W3C}.
```

Which displays as:

#figure(
image("snippet-<HASH>.png", width: 65%),
)

Of course, this also works on this #ts-acr("HTML") site. Try hovering over the abbreviations.

Acronyms are collected automatically during the #ts-logo("LaTeX") pass:

```
$ uv run texsmith test.md -tarticle 1>/dev/null
$ rg newacronym build/test.tex
92:\newacronym{HTML}{HTML}{HyperText Markup Language}
93:\newacronym{W3C}{W3C}{World Wide Web Consortium}
```

= Front-matter glossary

For longer documents you can declare acronyms under `press.declare.glossary` in
the YAML front matter. Each entry carries an explicit description and may be
attached to a group; TeXSmith renders one localised `\printglossary` table per
group (in declaration order) followed by a default table for ungrouped entries.
The `*[KEY]: …` body syntax keeps working and merges with the front-matter
entries.

```yaml
---
press:
  declare:
    glossary:
      style: long           # default; any glossaries-package style works
      groups:
        technique: Acronymes techniques
        institutionnel: Acronymes institutionnels
      entries:
        API:
          group: technique
          description: Application Programming Interface
        ONU:
          group: institutionnel
          description: Organisation des Nations Unies
        DOI: Digital Object Identifier   # short form: ungrouped, description only
---
```

A top-level `glossary:` key is the deprecated spelling; `tmark lint –fix`
moves it under `press.declare`.

The section is validated with pydantic, so unknown keys, missing descriptions,
or references to undeclared groups raise a clear error at conversion time. The
default acronym-table title follows the document language (it expands to
`\acronymname` from the `glossaries` package, which is localised by `babel`).

== Automatic substitution and limitations

Unlike #ts-logo("LaTeX"), TeXSmith does *not* require `\gls{…}` / `\Gls{…}` calls in the
source: the converter scans the body and replaces every *strict, case-sensitive*
match of an acronym key with `\acrshort{KEY}`. As a consequence, casing helpers
such as `\Gls`, `\GLS`, `\acrlong`, etc. are not synthesised — the substitution
is the same regardless of where the acronym appears in the text. If you need
those forms, drop down to a raw passthrough:
`{raw latex}(\Gls{KEY})`.

#v(1em)
#heading(numbering: none)[Acronyms]

/ HTML: HyperText Markup Language
