# Managing Slots

Slots are placeholders in the LaTeX template where specific document sections can be injected. Use the `--slot` (or `-s`) option to map input documents to these slots. For example, to inject `abstract.md` into the `abstract` slot and `dedication.md` into the `dedication` slot of a book template, run:

```bash
texsmith abstract.md dedication.md chapter*.md \
  --template book \
  --slot abstract:abstract.md \
  --slot dedication:dedication.md
```

To see the available slots for a given template, use the `--list-slots` flag:

```text
$ uv run texsmith -tbook --template-info
...
                                     Slots
┌────────────┬─────────┬───────────┬─────────┬────────┬────────────┬───────────┐
│            │         │      Base │         │        │  Effective │   Strip   │
│ Name       │ Default │     Level │   Depth │ Offset │      Level │  Heading  │
├────────────┼─────────┼───────────┼─────────┼────────┼────────────┼───────────┤
│ appendix   │         │         - │ chapter │      0 │          0 │    no     │
│ backmatter │         │         - │ chapter │      0 │          0 │    no     │
│ colophon   │         │         - │ chapter │      0 │          0 │    yes    │
│ dedication │         │         - │ chapter │      0 │          0 │    yes    │
│ frontmatt… │         │         - │ chapter │      0 │          0 │    no     │
│ mainmatter │    *    │         - │ chapter │      0 │          0 │    no     │
│ preface    │         │         0 │       - │      0 │          0 │    no     │
└────────────┴─────────┴───────────┴─────────┴────────┴────────────┴───────────┘
```

You can also extract sections from a single document using the `slot:Section Name` syntax. For example, to inject the "Abstract" section from `main.md` into the `abstract` slot:"

```bash
texsmith main.md \
  --template article \
  --slot abstract:slot:Abstract
```
