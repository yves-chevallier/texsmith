---
title: Nested Lists
subtitle: Six levels deep
author: TeXSmith
press:
  template: book
  language: english
---

# Deep nesting

Markdown nests a list as deeply as its author indents it. LaTeX stops at four
levels of `itemize`, four of `enumerate` and six lists of any kind inside one
another, and says `Too deeply nested`. The `texsmith-lists` package the
templates share lifts both limits to nine levels; this page walks to six.

## Bullets

- Level one
    - Level two
        - Level three
            - Level four
                - Level five
                    - Level six

## Numbers

1. Level one
    1. Level two
        1. Level three
            1. Level four
                1. Level five
                    1. Level six

## Mixed

1. An ordered outline
    - with a bullet under it
        1. and a number under that
            - and a bullet again
                1. and a fifth level
                    - and a sixth
