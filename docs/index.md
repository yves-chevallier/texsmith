# Welcome to TeXSmith

**TeXSmith** turns [Markdown](https://www.markdownguide.org/) into
press-ready [LaTeX](https://www.latex-project.org/). Keep your
docs authored in English-first Markdown, then compile polished PDFs for print,
journals, or long-form review packages—without maintaining two sources of truth.

![TexSmith Logo](assets/logo-full.svg){ width="60%" }

Optimized for MkDocs, the TeXSmith MkDocs plugin seamlessly integrates into your
documentation pipeline.

You can use TeXSmith to generate academic papers, technical reports, letters,
minutes, or class materials with diagrams, tables, citations, and code snippets.

## Why would I use TeXSmith?

TeXSmith bridges the gap between lightweight Markdown authoring
and the typographic power of LaTeX. It is ideal for:

- Writing a scientific article.
- Writing product documentation.
- Writing a book.
- Writing a letter.
- Writing cooking recipes.
- Writing technical reports.

The combination with MkDocs provides a single source of truth for both web and PDF output, which improves collaboration because all documentation lives in Markdown in a Git repository. Versioning with MkDocs stays simple and natural.

## Why teams choose TeXSmith

MkDocs native
: Handles Material-specific markup, pymdown extensions, and
  MkDocs plugins that tweak HTML in-flight.

Pipeline parity
: The CLI and Python API share the same conversion engine,
  so automation scripts and ad-hoc conversions stay in sync.

Template friendly
: Wrap multiple documents into a single LaTeX project,
  map fragments into template slots, and customise the runtime with Jinja2.

Diagnostics you can trust
: Structured emitter APIs and CLI verbosity
  flags surface the context you need when something goes wrong.

!!! note "LaTeX distribution"
    TeXSmith only generates LaTeX sources. Use TeX Live, MiKTeX, or MacTeX when
    you need PDFs (`texsmith --build` orchestrates Tectonic by default, or latexmk when requested).

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

## Quick start

=== "CLI"

    ````bash
    uv tool install texsmith  # or `pip install texsmith`

    cat <<'EOF' > intro.md
    # Demo Article

    Welcome to **TeXSmith**. See @fig:diagram.

    ```mermaid
    %% Diagram caption
    flowchart LR
        A[Markdown] --> B[HTML]
        B --> C[LaTeX]
    ```
    EOF

    texsmith intro.md --output build/
    ````

=== "Python"

    ```python
    from pathlib import Path

    from texsmith import Document, convert_documents

    docs = [Document.from_markdown(Path("intro.md"))]
    bundle = convert_documents(docs, output_dir=Path("build"))
    print(bundle.combined_output()[:200])
    ```

Both flows produce a LaTeX fragment in `build/intro.tex`. Add the `--template`
flag or `render_dir` to go straight to a print-ready project.

!!! tip "Rendering diagrams"
    Mermaid, Draw.io, and other rich diagrams rely on optional converters. The
    built-in Mermaid strategy expects Docker with the `minlag/mermaid-cli`
    image. Install it (or register a custom converter) to replace the fallback
    placeholder with rendered graphics.

## Works the way MkDocs authors write

- Markdown extensions mirror MkDocs Material out of the box.
- The single `texsmith` command exposes every pipeline primitive via flags
  (`--template`, `--build`, `--list-bibliography`, `--list-extensions`), keeping
  diagnostics close to the workflow.
- The Python API exposes the same runtime objects used internally, making it
  straightforward to integrate TeXSmith into CI pipelines or publishing tools.

## Architecture at a glance

| Layer    | Primary modules                                                | Highlights                                                                 |
| -------- | -------------------------------------------------------------- | -------------------------------------------------------------------------- |
| UI       | `texsmith.ui.cli`                                              | Typer-based CLI with Rich diagnostics and slot-aware options               |
| API      | `texsmith.api`                                                 | Author-friendly façade: `Document`, `ConversionService`, `TemplateSession` |
| Engine   | `texsmith.core.conversion`, `texsmith.core.templates`          | HTML→LaTeX renderer, template runtime, diagnostics                         |
| Adapters | `texsmith.adapters.markdown`, `texsmith.adapters.transformers` | Markdown normalisation and asset converters (Mermaid, Draw.io, Svgbob)     |

For a deeper dive, start with [High-Level Workflows](api/high-level.md) and move
on to [Core Engine](api/core.md) once you need fine-grained control.

## Next steps

- **New to TeXSmith?** Head to the [Quick Start guide](guide/getting-started.md).
- **Need CLI details?** Browse the [Command-line Overview](cli/index.md) and
  its subcommand pages.
- **Building your own template?** See [High-Level Workflows](api/high-level.md)
  for template walkthroughs, then dive into the API reference.
