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

#ts-callout-style.update("fancy")

`[[Page Title]]` belongs to the PyMdownX compatibility profile, not to TMark:
there is no wiki-link node, and the printer never emits the spelling. It is
listed as sugar for a link to the project file of that name.

```md
[[Getting Started]]

[[Subfolder/Page Title|Custom label]]
```

- The portion before the pipe names a Markdown file (`Getting Started` #ts-script("symbols")[→]
`getting-started.md`).
- Anything after `|` is the link text.

#ts-callout(kind: "warning", title: [Not implemented yet])[
The parser recognises the spelling and reports `compat-unsupported`: the
text stays literal rather than becoming a link. Do not rely on it in a
document meant for print.]

The canonical spelling is the link itself, which every renderer understands and
whose broken targets are visible rather than silent:

```md
[Getting Started](getting-started.md)

[Custom label](subfolder/page-title.md)
```

An empty-text link to another file (`[](getting-started.md)`) resolves to that
document's section number in print — see References.
