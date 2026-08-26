# Custom counters

This example demonstrates the `counters:` front-matter section in TeXSmith.
A short firmware review report declares two series — findings formatted as
`FW-{n:02d}` and requirements as `REQ-{n:03d}` starting at 100 — defines their
items with `#{prefix:key}` in table cells and in running prose, attaches one
silently to a heading with `{#prefix:key}`, and links them with `@prefix:key`
both forwards and backwards. A closing note shows that a marker whose prefix is
undeclared, such as a Ruby interpolation, is left untouched.

```bash
make           # build the LaTeX and the Typst PDF
make latex     # LaTeX only
make typst     # Typst only
```
