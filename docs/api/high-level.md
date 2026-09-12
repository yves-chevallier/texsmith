---
title: High-Level Workflows
---

# High-Level Workflows

TeXSmith exposes a thin, expressive façade over the lower-level conversion primitives. Mix and match Markdown, HTML, and template-aware documents without touching the CLI or re-implementing glue code.

This page showcases the building blocks you are most likely to use in scripts, services, or notebooks. All examples assume `pip install texsmith` (or `uv tool install texsmith`) plus any template packages you rely on.

!!! tip "Run the snippets"
    Save the examples into a file and execute them with `uv run python example.py`. The snippets rely only on fixtures you create alongside the script.

## Convert a handful of documents

Use `Document.from_markdown` / `Document.from_html` to normalise inputs, then hand everything to `convert_documents`. The bundle returned by `convert_documents` keeps every fragment, output path, and the raw LaTeX handy:

```python
from pathlib import Path

from texsmith import Document, convert_documents

docs = [
    Document.from_markdown(
        Path("foo.md"),
        base_level="section",  # named levels map to LaTeX sectioning commands
    ),
    Document.from_markdown(Path("bar.md"), base_level=0),
    Document.from_html(Path("baz.html"), selector="main.article__content"),
]

bundle = convert_documents(docs, output_dir=Path("build"))

print("Combined LaTeX:\n", bundle.combined_output())
for fragment in bundle.fragments:
    print("Rendered fragment", fragment.stem, "→", fragment.output_path)
```

`from_markdown` parses the source with tmark into `Document.ir`; `from_html`
reads an `.html` file into the same IR through the HTML reader, which is why
`selector`, `parser` and `full_document` only exist there. There is no `reader`
argument on either: a Markdown source has exactly one reader.

`ConversionRequest` carries conversion settings (selector, asset handling, manifest emission, etc.) in addition to document inputs. When you omit `output_dir`, the bundle stays in memory—perfect for unit tests or further processing.

Use it to opt into legacy LaTeX accent macros (default is Unicode output):

```python
from pathlib import Path

from texsmith import ConversionRequest, convert_documents, Document

settings = ConversionRequest(legacy_latex_accents=True)
bundle = convert_documents([Document.from_markdown(Path("intro.md"))], settings=settings)
```

## Drive the pipeline with `ConversionService`

If you need the exact orchestration used by the CLI, rely on `ConversionService`. It exposes two steps:

1. `prepare_documents(request)` splits inputs, parses each one into its IR, applies slot assignments, and returns a prepared batch.
2. `execute(request, prepared=...)` runs the passes, resolves once, writes one body per slot, wraps them in the template, and produces a `ConversionResponse` with the bundle plus emitted diagnostics.

A third step, `build_pdf(render_result, engine=...)`, hands the rendered project to Tectonic, latexmk or the Typst compiler.

```python
from pathlib import Path

from texsmith import ConversionRequest, ConversionService
from texsmith.core.diagnostics import LoggingEmitter

service = ConversionService()
request = ConversionRequest(
    documents=[Path("index.html")],
    selector="article.md-content__inner",
    template="article",
    render_dir=Path("build"),
    bibliography_files=[Path("refs.bib")],
    persist_debug_ir=True,  # keep each document's <stem>.ir.json
    emitter=LoggingEmitter(),
)
prepared = service.prepare_documents(request)
response = service.execute(request, prepared=prepared)

print("Main TeX:", response.render_result.main_tex_path)
for record in response.documents[0].diagnostics:
    print(record.severity, record.code, record.message)
```

Diagnostics reach a caller two ways: as they happen, through the emitter passed
on `ConversionRequest.emitter` (the CLI passes a `CliEmitter`, libraries get the
silent `NullEmitter` by default, `LoggingEmitter` forwards to `logging`); and
afterwards, as the `Diagnostic` records kept on each `Document`. `--strict`,
`--deprecated` and `--diagnostics-json` are the CLI's own reading of those same
records, not fields of the request.

`response.result` is a `ConversionBundle` without a template and a
`TemplateRenderResult` with one; `response.bundle` and `response.render_result`
are the guarded accessors, and `response.is_template` says which applies.

## Work with templates programmatically

`TemplateSession` wraps template discovery, option management, slot assignments, and final rendering (the heavy lifting lives in `texsmith.core.conversion.renderer.TemplateRenderer`).  Anything you can do from the CLI works here too, but you get a richer, Pythonic surface:

```python
from pathlib import Path

from texsmith import Document, TemplateSession, get_template

session = get_template("article")

# Configure template defaults (auto-completion friendly)
options = session.get_default_options()
options["title"] = "A Binder of Multiple Files"
options["author"] = "Your Name"
options["date"] = "2024-06-01"
session.set_options(options)

# Prepare documents
foo = Document.from_markdown(Path("foo.md"))
abstract = Document.from_markdown(Path("abstract.md"), strip_heading=True)

session.add_document(foo)
session.add_document(abstract, slot="abstract")

result = session.render(Path("outdir"))
print("Main TeX file:", result.main_tex_path)
print("LaTeX fragments:", result.fragment_paths)
print("Template engine:", result.template_engine)
```

Need bibliography support? Register `.bib` files with `session.add_bibliography(...)` before calling `render`. Every slot override (`Document.assign_slot`) and metadata tweak flows straight through to the template runtime.

!!! note
    For practical slot recipes (front matter/main matter splits, appendix routing, overrides) see the [Template Cookbook](../guide/templates/template-cookbook.md).

## Reuse the same plumbing as the CLI

`texsmith` relies on these high-level primitives. Inspect the CLI command and you will notice the same API surface shown above. Scripts and command-line invocations stay aligned, and new features land in one place.

For a complete reference, browse the API browser or explore the source directly in `src/texsmith/core/`.

!!! seealso
    - [Command-line Overview](../cli/index.md) explains how these APIs surface through Typer commands.
    - [Core Engine](core.md) documents the lower-level modules if you need to plug into diagnostics or templating internals.
