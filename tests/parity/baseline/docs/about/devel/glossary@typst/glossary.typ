#set document(
title: "Glossary",
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
#text(size: 1.8em, weight: "bold")[Glossary]]
#v(1.5em)

#ts-callout-style.update("fancy")

The MkDocs #link("https://realtimeprojects.github.io/mkdocs-ezglossary")[ezglossary] plugin exists, but the syntax is unintuitive (for example, the semicolon separator) and does not handle spaced or formatted entries well. Ideally, readers should be able to access the glossary as a popup, tooltip, or link.

#ts-logo("LaTeX") glossaries usually rely on the `glossaries` package and definitions declared in the preamble via `\newglossaryentry`:

```latex
\newglossaryentry{key}{
  name={singular form},
  plural={plural form},
  description={descriptive text},
  first={special form for first use},
  text={normal form (if you want to force it)},
}
```

`\gls` uses the standard form, `\Gls` capitalizes the first letter, `\glspl` gives the plural, and `\Glspl` capitalizes the plural. The first use of the term falls back to the `first` form when present, otherwise `name`. Markdown alone cannot express all of that. *What shipped* is the front-matter
declaration, under `press.declare.glossary` (the top-level `glossary:` key is
read as deprecated sugar):

```yml
press:
  declare:
    glossary:
      entries:
        HTML: HyperText Markup Language
```

Every occurrence of a declared key in the prose becomes `\tsacr{HTML}`, which
`ts-glossary` defines as `\acrshort` — always the short form, deliberately: the
author never writes the call, so a first-use expansion would rewrite prose
nobody typed and make the printed document say something different from the web
profile, where the key stays inside `<abbr>`. A glossary _term_ reference is
written by the author as `@gls:term` and becomes `\tsgls`, which is `\gls` and
therefore follows the `glossaries` conventions.

What is *still open* is the rest of a `\newglossaryentry`: `plural`, `first`
and a forced `text` have no spelling yet, and neither does the popup/tooltip
presentation on the web side.
