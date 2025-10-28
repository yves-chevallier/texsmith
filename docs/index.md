# Welcome to TeXSmith

TeXSmith turns Markdown written for MkDocs into press-ready LaTeX. Keep your
docs authored in English-first Markdown, then compile polished PDFs for print,
journals, or long-form review packages—without maintaining two sources of truth.

## Why teams choose TeXSmith

- **MkDocs native** – Handles Material-specific markup, pymdown extensions, and
  MkDocs plugins that tweak HTML in-flight.
- **Pipeline parity** – The CLI and Python API share the same conversion engine,
  so automation scripts and ad-hoc conversions stay in sync.
- **Template friendly** – Wrap multiple documents into a single LaTeX project,
  map fragments into template slots, and customise the runtime with Jinja2.
- **Diagnostics you can trust** – Structured emitter APIs and CLI verbosity
  flags surface the context you need when something goes wrong.

!!! note "LaTeX distribution"
    TeXSmith only generates LaTeX sources. Use TeX Live, MiKTeX, or MacTeX when
    you need PDFs (`texsmith build` orchestrates `latexmk` for you).

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

    texsmith convert intro.md --output build/
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

- Markdown extensions mirror MkDocs Material out of the box. See
  [Supported Markdown Syntax](markdown/supported.md) for the full list.
- CLI subcommands (`convert`, `build`, `bibliography`) map directly to pipeline
  primitives and include instant diagnostics (`--debug`, `--verbose`, and
  `--list-extensions`).
- The Python API exposes the same runtime objects used internally, making it
  straightforward to integrate TeXSmith into CI pipelines or publishing tools.

## Architecture at a glance

| Layer | Primary modules | Highlights |
| --- | --- | --- |
| UI | `texsmith.ui.cli` | Typer-based CLI with Rich diagnostics and slot-aware options |
| API | `texsmith.api` | Author-friendly façade: `Document`, `ConversionService`, `TemplateSession` |
| Engine | `texsmith.core.conversion`, `texsmith.core.templates` | HTML→LaTeX renderer, template runtime, diagnostics |
| Adapters | `texsmith.adapters.markdown`, `texsmith.adapters.transformers` | Markdown normalisation and asset converters (Mermaid, Draw.io, Svgbob) |

For a deeper dive, start with [High-Level Workflows](api/high-level.md) and move
on to [Core Engine](api/core.md) once you need fine-grained control.

## Next steps

- **New to TeXSmith?** Head to the [Quick Start guide](getting-started/getting-started.md).
- **Need CLI details?** Browse the [Command-line Overview](cli/index.md) and
  its subcommand pages.
- **Building your own template?** See [High-Level Workflows](api/high-level.md)
  for template walkthroughs, then dive into the API reference.
