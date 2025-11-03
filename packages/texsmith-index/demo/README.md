# Index Demo

This directory demonstrates how to combine the three components shipped with
`texsmith-index`:

1. **Markdown** – the syntax `#[tag0][tag1][tag2]{style}` marks positions that
   should become index entries.
2. **TeXSmith** – during the LaTeX conversion (using the `article` template) the
   tagged spans turn into `\index{...}` commands and automatically enable
   `imakeidx` with the xindy backend.
3. **MkDocs** – the plugin augments the lunr search index with the collected
   tags so readers can locate indexed concepts in the web documentation.

## Quick start

```bash
cd packages/texsmith-index/examples/index-demo
uv pip install ../../../.. ../../../../templates/article
uv run mkdocs build
```

The MkDocs plugin writes the LaTeX sources to `press/index.tex`. Generate the
PDF with `latexmk`:

```bash
cd press
latexmk -pdf index.tex
```

The resulting document includes an index compiled with xindy while the MkDocs
site surfaces the same tags in the search UI.
