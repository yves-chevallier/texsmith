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

![Workflow diagram of TeXSmith](../assets/workflow.drawio)

## How is it different from Pandoc?

Pandoc is a powerhouse, but reproducing a Material-flavoured MkDocs site in
Pandoc requires custom filters and maintenance. TeXSmith focuses on MkDocs
parity out of the box:

- Handles Material-only components such as tabbed content, callouts, and
  keyboard keys.
- Ships with diagram converters (Mermaid, Draw.io, Svgbob) that plug directly
  into the LaTeX build step.
- Exposes the same primitives via the CLI and Python API, so automation scripts
  match what authors do locally.

Use both tools together when it makes sense; reach for TeXSmith when MkDocs → LaTeX
compatibility is the priority.

## Project status

TeXSmith is under active development and gearing up for a 1.0 release. The
conversion pipeline is stable across real-world MkDocs sites, but you should
expect ongoing improvements to templates, diagram strategies, and diagnostics.

!!! info "Give feedback"
    Found a gap or an edge case? Open an issue or PR—most new features come from
    teams converting documentation sets in the wild.
