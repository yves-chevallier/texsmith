#set document(
title: "Cooking Recipes",
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
#text(size: 1.8em, weight: "bold")[Cooking Recipes]]
#v(1.5em)

TeXSmith isn’t just for papers and slides – it can plate up gorgeous recipes straight from structured data. Here’s a French walnut cake expressed as YAML, pushed through a custom `recipe` template. Click the card to grab the PDF.

#figure(
image("snippet-<HASH>.png", width: 60%),
caption: [Demo],
)

The authoring surface is pure data: *YAML* fields flow into a #ts-logo("LaTeX") template, no Markdown gymnastics required. Swap the YAML for a DB/API payload and you’ve got a pipeline-ready recipe generator for your site or app.

#ts-div("tab", title: "cake.yml")[
```yaml
[include: examples/recipe/cake.yml not found]
```]

#ts-div("tab", title: "manifest.toml")[
```toml
[include: examples/recipe/manifest.toml not found]
```]

#ts-div("tab", title: "template.tex")[
```tex
[include: examples/recipe/template.tex not found]
```]

#ts-callout(kind: "note")[
The recipe layout used in this template was inspired by the Cours de cuisine created by M.-C. Bolle back in 1978. She produced an exceptional cookbook for the Department of Public Instruction of the Canton of Geneva, Switzerland.

I’ve never seen recipes presented quite this way anywhere else – it’s a uniquely clever system – but I find it incredibly practical and efficient.]
