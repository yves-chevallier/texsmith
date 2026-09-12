#set document(
title: "LaTeX",
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
#text(size: 1.8em, weight: "bold")[LaTeX]]
#v(1.5em)

The #ts-logo("LaTeX") body itself comes from tmark's writer; what stays on the Python side
is the escaping table the templates and fonts reuse, the asset plumbing, the
Pygments bridge of the `highlight` pass, and the template runtime.
