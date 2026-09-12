#set document(
title: "Build",
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
#text(size: 1.8em, weight: "bold")[Build]]
#v(1.5em)

To build your #ts-logo("LaTeX") document into a PDF, use the `–build` (or `-b`) option. This command compiles the generated #ts-logo("LaTeX") file using the default engine. TeXSmith uses `tectonic` by default as it is the only self-contained #ts-logo("LaTeX") engine, but you can configure it to use `lualatex` or `xelatex` via `latexmk` if preferred. Here is an example of a simple document built with different engines:

```bash
$ uv run texsmith cheese.md cheese.bib -tarticle --build --engine=xelatex
$ uv run texsmith cheese.md cheese.bib -tarticle --build --engine=lualatex
$ uv run texsmith cheese.md cheese.bib -tarticle --build --engine=tectonic
```
