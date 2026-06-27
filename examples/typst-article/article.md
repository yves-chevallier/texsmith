---
title: A Typst Article
---

# Introduction

This article exercises the **covered subset** of the *Typst* backend: it is
produced from the same intermediate representation (IR) the other backend
consumes, proving the architecture supports a second writer without touching
the reader. Here is some ~~struck-through~~ text and a piece of `inline code`.

A second paragraph keeps the document a little longer so the layout has more
than one block of prose to typeset.

## Inline formatting

You can combine *emphasis*, **strong emphasis**, and `code`. External links
look like [the Typst website](https://typst.app). Inline math such as
\(a^2 + b^2 = c^2\) flows in the text.

## Lists

An unordered list:

- first item
- second item with nested points
    - nested one
    - nested two
- third item

An ordered list:

1. step one
2. step two
3. step three

## A block quote

> The IR is a pure tree; the writer chooses the backend syntax.

## Code

```python
def greet(name):
    print(f"Hello, {name}!")
```

## Mathematics

A display equation:

$$
E = m c^2
$$

## A simple table

| Language | Year |
|----------|------|
| Markdown | 2004 |
| Pandoc   | 2006 |

---

The end.
