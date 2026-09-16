---
title: Box Drawing
subtitle: Tree diagrams inside a listing
author: TeXSmith
press:
  template: article
  language: english
---

# Diagrams drawn in a listing

A listing that draws a tree uses the Unicode *Box Drawing* block, and a
progress bar the *Block Elements* one. No text font carries either, so the
document takes them from a monospace fallback — at the advance width of the
column they sit in, which is what keeps a tree's stems under one another.

```text
project
├── src
│   ├── main.c
│   └── util.c
└── tests
    └── main_test.c

┌───┬───┐
│ a │ b │
├───┼───┤
│ c │ d │
└───┴───┘

[████████░░░░] 66%
```

A Greek letter in a listing comes from the same machinery: `eps = ε` is the
epsilon of `if (fabs(x) < ε)`, and it is a fallback away from the monospace
face too.

```c
double eps = 1e-9; /* ε */
```
