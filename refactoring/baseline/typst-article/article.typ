#set page(margin: 2.5cm)
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true)

#align(center)[#text(size: 1.6em, weight: "bold")[A Typst Article]]
#v(1em)

= Introduction

This article exercises the *covered subset* of the _Typst_ backend: it is
produced from the same intermediate representation (IR) the other backend
consumes, proving the architecture supports a second writer without touching
the reader. Here is some #strike[struck-through] text and a piece of `inline code`.

A second paragraph keeps the document a little longer so the layout has more
than one block of prose to typeset.

== Inline formatting

You can combine _emphasis_, *strong emphasis*, and `code`. External links
look like #link("https://typst.app")[the Typst website]. Inline math such as
$a^2 + b^2 = c^2$ flows in the text.

== Lists

An unordered list:

- first item
- second item with nested points
  - nested one
  - nested two
- third item

An ordered list:

+ step one
+ step two
+ step three

== A block quote

#quote(block: true)[
  The IR is a pure tree; the writer chooses the backend syntax.
]

== Code

```python
def greet(name):
    print(f"Hello, {name}!")
```

== Mathematics

A display equation:

$ E = m c^2 $

== A simple table

#table(
  columns: 2,
  align: (left, left),
  table.header([Language], [Year]),
  [Markdown], [2004],
  [Pandoc], [2006],
)

#line(length: 100%)

The end.
