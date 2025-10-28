# TeXSmith

[![CI](https://github.com/yves-chevallier/texsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/yves-chevallier/texsmith/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/yves-chevallier/texsmith/branch/main/graph/badge.svg)](https://codecov.io/gh/yves-chevallier/texsmith)
[![PyPI](https://img.shields.io/pypi/v/texsmith.svg)](https://pypi.org/project/texsmith/)
[![Repo Size](https://img.shields.io/github/repo-size/yves-chevallier/texsmith.svg)](https://github.com/yves-chevallier/texsmith)
[![Python Versions](https://img.shields.io/pypi/pyversions/texsmith.svg?logo=python)](https://pypi.org/project/texsmith/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)

![MkDocs](https://img.shields.io/badge/MkDocs-1.6+-blue.svg?logo=mkdocs)
![MkDocs Material](https://img.shields.io/badge/MkDocs%20Material-supported-success.svg?logo=materialdesign)
![Python](https://img.shields.io/badge/Python-typed-blue.svg?logo=python)

TeXSmith is a [Python](https://www.python.org/) package and CLI tool to convert **Markdown** or **HTML** documents into LaTeX format. It is designed to be extensible via templates and integrates with [MkDocs](https://www.mkdocs.org/) for generating printable documents from documentation sites.

<p align="center">
<img src="docs/assets/logo-full.svg" width="70%" />
</p>

## TL;DR

```bash
pip install texsmith
texsmith convert input.md input.bib -o article/ --template nature
```

## Project layout

The source tree is organised around three top-level namespaces:

- `texsmith.core` contains the conversion pipeline, document models, diagnostics, and template helpers.
- `texsmith.adapters` hosts infrastructure integrations such as Markdown parsing, LaTeX rendering, Docker helpers, and transformer utilities.
- `texsmith.ui` provides end-user interfaces, including the Typer-powered CLI.

## Core architecture highlights

- `ConversionService` encapsulates the orchestration that previously lived in `texsmith.api.service` helpers. Provide a `ConversionRequest` and receive a `ConversionResponse` with rendered bundles and diagnostics.
- `TemplateRenderer` now owns slot aggregation and LaTeX assembly. `TemplateSession` focuses on session state, template options, and bibliography tracking.
- `DocumentSlots` unify slot directives from front matter, CLI flags, and programmatic overrides. Every entry point now speaks the same data model.
- `DiagnosticEmitter` replaces ad-hoc callback bags so warnings, errors, and structured events flow through a predictable interface (CLI uses `CliEmitter`; libraries can plug in their own).

### Programmatic conversions with `ConversionService`

```python
from pathlib import Path

from texsmith.api.service import ConversionRequest, ConversionService

service = ConversionService()
request = ConversionRequest(
    documents=[Path("docs/index.html")],
    bibliography_files=[Path("references.bib")],
    template="article",
    render_dir=Path("build"),
)
prepared = service.prepare_documents(request)
response = service.execute(request, prepared=prepared)

print("Main TeX:", response.render_result.main_tex_path)
print("Diagnostics:", [event.name for event in response.diagnostics])
```

If you only need a quick conversion, the high-level helpers (`texsmith.Document`, `texsmith.convert_documents`, `texsmith.TemplateSession`) continue to work, but they now reuse the same ConversionService plumbing as the CLI.

> Refer to `UPGRADE.md` for release notes and migration guidance from earlier builds.

## Render engine phases

The rendering pipeline walks the BeautifulSoup tree four times. Each pass maps
to a value of `RenderPhase` so handlers can opt into the point where their
transform should fire:

- `RenderPhase.PRE`: Early normalisation. Use it to clean the DOM and
  replace nodes before structural changes happen (e.g. unwrap unwanted tags,
  turn inline `<code>` into LaTeX).
- `RenderPhase.BLOCK`: Block-level transformations once the tree structure
  is stable. Typical consumers convert paragraphs, lists, or blockquotes into
  LaTeX environments.
- `RenderPhase.INLINE`: Inline formatting where block layout is already
  resolved. It is the right place for emphasis, inline math, or link handling.
- `RenderPhase.POST`: Final pass after children are processed. Use it for
  tasks that depend on previous passes such as heading numbering or emitting
  collected assets.
