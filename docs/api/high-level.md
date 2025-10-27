---
title: High-Level Workflows
---

# High-Level Workflows

The new `texsmith.api` package provides a thin, expressive façade over the lower-level conversion primitives.  You can mix and match Markdown, HTML, and template-aware documents without touching the CLI or re-implementing the tedious glue code that used to live in older CLI helpers.

This page showcases the building blocks you are most likely to use in your own scripts, services, or notebooks.  All the examples assume `pip install texsmith` and any template packages you rely on.

## Convert a handful of documents

Use `Document.from_markdown` / `Document.from_html` to normalise inputs, then hand everything to `convert_documents`.  The bundle returned by `convert_documents` keeps every fragment, output path, and the raw LaTeX handy:

```python
from pathlib import Path

from texsmith import Document, HeadingLevel, RenderSettings, convert_documents

docs = [
    Document.from_markdown(
        Path("foo.md"),
        heading=HeadingLevel.section,  # named levels map to LaTeX sectioning commands
    ),
    Document.from_markdown(Path("bar.md"), heading=0),
    Document.from_html(Path("baz.html"), selector="main.article__content"),
]

bundle = convert_documents(docs, output_dir=Path("build"))

print("Combined LaTeX:\n", bundle.combined_output())
for fragment in bundle.fragments:
    print("Rendered fragment", fragment.stem, "→", fragment.output_path)
```

`RenderSettings` lets you fine-tune the engine (parser, fallbacks, manifest emission, etc.).  When you omit `output_dir`, the bundle stays in memory – perfect for unit tests or further processing.

## Drive the pipeline with `ConversionService`

If you need the exact orchestration used by the CLI, rely on `ConversionService`.  It exposes two steps:

1. `prepare_documents(request)` splits inputs, normalises Markdown/HTML, applies `DocumentSlots`, and returns a `ConversionPrepared` payload.
2. `execute(request, prepared=...)` renders the documents, optionally through a template, and produces a `ConversionResponse` with the bundle plus emitted diagnostics.

```python
from pathlib import Path

from texsmith.api.service import ConversionRequest, ConversionService

service = ConversionService()
request = ConversionRequest(
    documents=[Path("index.html")],
    selector="article.md-content__inner",
    template="article",
    render_dir=Path("build"),
    bibliography_files=[Path("refs.bib")],
    debug=True,
)
prepared = service.prepare_documents(request)
response = service.execute(request, prepared=prepared)

for event in response.diagnostics:
    print(event.name, event.payload)
```

The CLI passes a `CliEmitter` via `ConversionRequest.emitter` so warnings surface nicely.  Library callers can supply their own emitter or accept the default `NullEmitter`.

## Work with templates programmatically

`TemplateSession` wraps template discovery, option management, slot assignments, and final rendering (the heavy lifting lives in `texsmith.core.conversion.TemplateRenderer`).  Anything you can do from the CLI works here too, but you get a richer, Pythonic surface:

```python
from pathlib import Path

from texsmith import Document, TemplateOptions, TemplateSession, get_template

session = get_template("article")

# Configure template defaults (auto-completion friendly)
options = session.get_default_options()
options.title = "A Binder of Multiple Files"
options.author = "Your Name"
options.date = "2024-06-01"
session.set_options(options)

# Prepare documents
default_extensions = None  # use built-in defaults
foo = Document.from_markdown(Path("foo.md"), extensions=default_extensions)
abstract = Document.from_markdown(Path("abstract.md"), extensions=default_extensions)
abstract.drop_title = True

session.add_document(foo)
session.add_document(abstract, slot="abstract")

result = session.render(Path("outdir"))
print("Main TeX file:", result.main_tex_path)
print("LaTeX fragments:", result.fragment_paths)
print("Template engine:", result.template_engine)
```

Need bibliography support?  Register `.bib` files with `session.add_bibliography(...)` before calling `render`.  Every slot override (`Document.assign_slot`) and metadata tweak flows straight through to the template runtime.

## Reuse the same plumbing as the CLI

Both `texsmith convert` and `texsmith build` now rely on these high-level primitives.  If you inspect the refactored CLI commands you will notice the same API surface shown above.  That means scripts and command line invocations stay perfectly aligned, and new features land in one place.

For a complete reference, browse [`texsmith.api`](core.md#texsmithapi) in the API browser or explore the source directly in `src/texsmith/api/`.
