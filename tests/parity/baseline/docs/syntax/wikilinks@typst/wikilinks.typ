#set document(
title: "Wiki Links",
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
#text(size: 1.8em, weight: "bold")[Wiki Links]]
#v(1.5em)

MkDocs and Python-Markdown support the `[[Wiki Link]]` syntax via the `wikilinks`
extension. TeXSmith keeps that behavior so you can link between pages without
remembering exact file paths.

```markdown
[[Getting Started]]
[[Subfolder/Page Title|Custom label]]
```

- The portion before the pipe resolves to a Markdown file (`Getting Started` #ts-script("symbols")[→]
`getting-started.md`).
- Anything after `|` becomes the rendered link text.
- When building PDFs, TeXSmith turns wiki links into standard hyperlinks, so the
references remain navigable.
