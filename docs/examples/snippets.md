# Snippet Blocks

TeXSmith renders fenced blocks with the `.snippet` class into PDF/PNG pairs and injects them into the page with a download link. Snippets now accept a concise YAML payload instead of `data-*` attributes, and the PNG preview is left unframed so you can wrap it with the `ts-frame` fragment when needed.

## YAML-driven snippets

Use a YAML fence to point TeXSmith at your sources, working directory, and extra template options. The width of the rendered preview comes from the fence attribute.

````md
```yaml {.snippet }
layout: 2x2
cwd: ../../examples/paper
sources:
  - cheese.md
  - cheese.bib
template: article
width: 70%
fragments:
  ts-frame
press:
  frame: true
```
````

- `cwd` is the directory where TeXSmith runs, resolving relative sources.
- `sources` mirrors the CLI arguments: Markdown inputs and auxiliary files like `.bib`.
- `layout` arranges multiple PDF pages on the preview grid.
- `press` merges into the template context (fragments, format, etc.).

## Inline Markdown with front matter

You can also render inline Markdown. Front matter drives the template choice and fragment selection while the body becomes the snippet content.

````md
```md {.snippet caption="Inline snippet" width="65%"}
---
template: snippet
fragments:
  ts-frame:
press:
  frame: true
---
# Section

Some content...
```
````

```md {.snippet caption="Inline snippet" width="65%"}
---
template: snippet
fragments:
  ts-frame:
press:
  frame: true
---
# Section

Some content...
```

## Reusing a config file

When the same snippet settings are shared across pages, point the fence to a YAML config and keep the block body empty or minimal.

````md
```md {.snippet config="snippet-configs/letter.yml" caption="Config-driven snippet" width="70%"}
```
````

The configuration lives alongside this page at `docs/examples/snippet-configs/letter.yml`.
