---
hide:
  - navigation
---
# Welcome to TeXSmith

**TeXSmith** turns [Markdown](https://www.markdownguide.org/) into
press-ready [LaTeX](https://www.latex-project.org/). Keep your
docs authored in Markdown, then compile polished PDFs for print,
journals, or long-form review packages—without maintaining several sources of truth. No need to learn LaTeX, install heavy toolchains, or wrestle with complex conversion setups.

![TexSmith Logo](assets/ts-light.svg#only-light){ width="50%" }
![TexSmith Logo](assets/ts-dark.svg#only-dark){ width="50%" }

Furthermore, TeXSmith is optimized for MkDocs thanks to the TeXSmith MkDocs plugin, which seamlessly integrates into your documentation pipeline.

You can use TeXSmith to generate academic papers, technical reports, letters,
minutes, or class materials with diagrams, tables, citations, and more.

![Pipeline](assets/pipeline.png)

## Why would I use TeXSmith?

TeXSmith bridges the gap between lightweight Markdown authoring
and the typographic power of LaTeX. It is ideal for:

- Writing scientific articles.
- Writing product documentation.
- Writing books.
- Writing letters.
- Writing technical reports.
- Writing cooking recipes and more.

The combination with MkDocs provides a single source of truth for both web and PDF output, which improves collaboration because all documentation lives in Markdown in a Git repository. Versioning with MkDocs stays simple and natural.

## Why teams choose TeXSmith

Pipeline parity
: The CLI and Python API share the same conversion engine,
  so automation scripts and ad-hoc conversions stay in sync.

Template friendly
: Wrap multiple documents into a single LaTeX project,
  map fragments into template slots, and customise the runtime with Jinja2.

Diagnostics you can trust
: Structured emitter APIs and CLI verbosity
  flags surface the context you need when something goes wrong.

## How is it different from Pandoc?

[Pandoc](https://pandoc.org/) is a powerhouse, but reproducing an extended Markdown syntax other than
[CommonMark](https://commonmark.org/) or [GitHub-flavored Markdown](https://github.github.com/gfm/) document in
Pandoc requires custom filters and ongoing maintenance. TeXSmith focuses on MkDocs Markdown
with Pymdown extensions, delivering parity out of the box:

- Handles Material-only components such as tabbed content, callouts, and
  keyboard keys.
- Ships with diagram converters (Mermaid, Draw.io) that plug directly
  into the LaTeX build step.
- Exposes the same primitives via the CLI and Python API, so automation scripts
  match what authors do locally.

Use both tools together when it makes sense; reach for TeXSmith when MkDocs → LaTeX
compatibility is the priority.
