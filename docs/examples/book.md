[](){ #einstein }

# Book

For this example we want to rendre homage to Albert Einstein and creating a small book using the [Wikipedia](https://en.wikipedia.org/wiki/Albert_Einstein)
as our source.

The text was converted to LaTeX then built using the `book` template.

This examples demonstrates the use of frontmatter for citations, abbreviations, glossary and index.

For this example we decided to use a small paper size (A5) and a sans serif font (Adventor). The book is structured in parts and specific slots are used for the colophon, dedication and preface. Here is the frontmatter used for this example:

```yaml
title: Albert Einstein
subtitle: His Life and Achievements
date: 2025-03-15
edition: Wikipedia Adaptation
author: Wikipedia Contributors
publisher: Wikipedia Sourcebooks
imprint:
  thanks: |
    Adapted from the Wikipedia article “Albert Einstein” (retrieved ).
    Thank you to the Wikipedia contributors whose work makes this example
    possible.
  copyright: |
    Wikipedia contributors. Text licensed under Creative Commons Attribution-ShareAlike
    International (CC BY-SA).
  license: |
    This TeXSmith example is derived from Wikipedia and is not affiliated
    with TeXSmith. Reuse must credit Wikipedia and share under CC BY-SA .
press:
  paper: a5
  template: book
  base_level: part
  fonts: adventor
  admonition_style: classic
  slots:
    colophon: Colophon
    dedication: Dedication
    preface: Preface
```

```yaml {.snippet}
layout: 4x2
cwd: ../../examples/book
sources:
  - book.md
  - book.bib
template: book
fragments:
  ts-frame:
press:
  frame: true
```

The example can independently be built using the CLI on the `examples/book/` folder. The engine can be chosen between `tectonic`, `xelatex` and `lualatex`
as follows:

```bash
texsmith book.md book.bib --template book --build --engine tectonic
```

The power of TeXSmith is to be able to generate such complex documents from simple Markdown with no LaTeX knowledge required and no LaTeX toolchain installed. Fonts, toolchain and image conversion are all handled automatically by TeXSmith in one single command.
