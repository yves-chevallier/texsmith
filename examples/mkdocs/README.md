# MkDocs book example

This example shows how to export a MkDocs site to LaTeX using the TeXSmith plugin. The configuration in `mkdocs.yml` defines a book with custom slots and paper size, then renders the LaTeX bundle under `press/demo/`.

## Prerequisites

- Dependencies installed via `uv sync` at the repository root.
- A LaTeX engine available for `latexmk` (used to compile the produced `.tex` file).

## Usage

- Build the site and the PDF from this directory:

  ```bash
  make
  ```

- Build only the LaTeX bundle without compiling to PDF:

  ```bash
  uv run mkdocs build
  ```

- Clean generated assets:

  ```bash
  make clean
  ```

You can also run `make all` from the repository-level `examples/Makefile` to build every example, including this one. Generated artifacts are collected in `examples_build/` when `ARTIFACTS_DIR` is set.
