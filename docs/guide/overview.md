# Overview

TeXSmith bridges Markdown-first documentation with LaTeX-first publishing.
Instead of rewriting material for print, you can promote the same MkDocs pages
into journals, reports, or classroom packs—complete with diagrams, tables, and
citations.





## What is TeXSmith?

TeXSmith is a Python toolchain that:

- Normalises Markdown (including Material and pymdown extensions) into a stable
  HTML structure.
- Converts that HTML into LaTeX while preserving semantic intent (admonitions,
  code annotations, tabbed content, callouts, and more).
- Bundles fragments together through a Jinja2-based template runtime so you can
  build full reports, slide decks, or multi-chapter manuals.

![Workflow diagram of TeXSmith](assets/workflow.drawio)