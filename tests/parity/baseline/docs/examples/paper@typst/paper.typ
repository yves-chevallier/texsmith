#set document(
title: "Research Paper",
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
#text(size: 1.8em, weight: "bold")[Research Paper]]
#v(1.5em)

#metadata(none) <cheese>

This example shows how TeXSmith can be used to write scientific papers with
Markdown source, bibliographies, and figures. It uses the `article` template
package, which provides a standard article layout with support for
citations, cross-references, and floating figures/tables.

The documentation preview uses the default A4 portrait layout. Click the image
to download the PDF.

#ts-code(class: ("snippet"), caption: "Download PDF")[
```yaml
width: 70%
fragments:
  ts-frame
press:
  frame: true
layout: 2x2
cwd: ../../examples/paper
sources:
  - cheese.md
  - cheese.bib
template: article
```]

Here is the source code for this example:

#ts-div("tab", title: "Article")[
```markdown
[include: docs/assets/examples/cheese.md not found]
```]

#ts-div("tab", title: "Bibliography")[
```bibtex
[include: docs/assets/examples/cheese.bib not found]
```]

To render the example manually:

```bash
texsmith cheese.md cheese.bib -tarticle --build
```

#ts-callout(kind: "info")[
Naturally, this article isn’t an actual research paper! It’s AI-generated
content cooked up purely for demo purposes. One reference _is_ real, though—the one
containing the original figure. I don’t own the rights to that figure; I simply
redrew it in vector form. All author names and the contents of the other references
are completely fictional. Any resemblance to real people or publications is
entirely coincidental… unless the cheese overlords say otherwise.]

#ts-callout(kind: "note")[
I came up with this example because: (1) as a Swiss person, cheese is basically
part of my operating system, and (2) when I was a student, a friend of mine did
his PhD on cheese and collected delightfully absurd cheese-related research that
nobody would imagine studying scientifically.

I initially thought about an article on how Swiss music—specifically yodeling—might
influence cheese ripening. But, well… rheology felt slightly more scientifically
defensible.]
