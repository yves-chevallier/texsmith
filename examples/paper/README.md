# Scientific Paper Example

This examples demonstrates how to use Markdown to write a scientific paper including tables, equations, and code snippets for computational modeling.

## Building the Example

```bash
texsmith cheese.md cheese.bib --template article --build
```

## Timing

| Engine   | Options  | Time (s) | File Size (KB) |
| -------- | -------- | -------- | -------------- |
| pdflatex | pygments | -        | 0              |
| xelatex  | pygments | 7.3      | 119            |
| lualatex | pygments | 25.6     | 117            |
| tectonic | pygments | 7.3      | 119            |
