# Abbreviations

Enable the `texsmith.abbr` extension and you can sprinkle definitions directly into your Markdown. Drop the abbreviation between square brackets, follow it with the expanded form in parentheses, and the parser does the rest.

```markdown
The HTML specification is maintained by the W3C.

*[HTML](HyperText Markup Language)
*[W3C](World Wide Web Consortium)
```

TeXSmith renders that snippet as:

```text
$ uv run texsmith abbr.md
The \acrshort{HTML} specification is maintained by the \acrshort{W3C}.
```

Acronyms are collected automatically during the LaTeX pass:

```text
$ uv run texsmith test.md -tarticle 1>/dev/null
$ rg newacronym  build/test.tex 
92:\newacronym{HTML}{HTML}{HyperText Markup Language}
93:\newacronym{W3C}{W3C}{World Wide Web Consortium}
```

## LaTeX Rendering

Below is a preview of how the abbreviations will appear in the rendered document:

[![Rendered acronym list](../assets/examples/abbreviations.png)](../assets/examples/abbreviations.pdf)
