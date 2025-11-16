# Abbreviations

When building with the `abbr` extension enabled, you can define abbreviations in your Markdown documents. An abbreviation is defined by placing the abbreviation in square brackets followed by the full form in parentheses.

```markdown
The HTML specification is maintained by the W3C.

*[HTML](HyperText Markup Language)
*[W3C](World Wide Web Consortium)
```

TeXSmith will render this as:

```text
$ uv run texsmith render abbr.md
The \acrshort{HTML} specification is maintained by the \acrshort{W3C}.
```

The abbreviations are automatically added to the list of acronyms in the LaTeX output:

```text
$ uv run texsmith render test.md -tarticle 1>/dev/null
$ rg newacronym  build/test.tex 
92:\newacronym{HTML}{HTML}{HyperText Markup Language}
93:\newacronym{W3C}{W3C}{World Wide Web Consortium}
```

## LaTeX Rendering

Below is a preview of how the abbreviations will appear in the rendered document:

[![Rendered acronym list](../assets/examples/abbreviations.png)](../assets/examples/abbreviations.pdf)

