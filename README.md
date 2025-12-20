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
<img src="docs/assets/ts-logo.svg" width="70%" />
</p>

## TL;DR

```bash
pip install texsmith
texsmith input.md input.bib -o build/ --build
```

## Key features

- **MkDocs-native Markdown** – Ships with the same Material + pymdown extension stack you use in MkDocs, so tabs, callouts, annotations, tooltips, and data tables survive the conversion.
- **Template-first runtime** – Bundle multiple fragments into slots, merge front matter metadata, and emit LaTeX projects ready for Tectonic or latexmk with Docker-friendly manifests.
- **CLI and Python parity** – The Typer-powered CLI wraps the same ConversionService you can consume as a library, making CI/CD and notebooks behave like local runs.
- **Actionable diagnostics** – Structured emitters, verbosity switches, and `--debug` traces keep LaTeX issues debuggable even in automated pipelines.
- **Extensible converters** – Override Markdown parsers, hook into RenderPhase handlers, or ship diagram transformers (Mermaid, Draw.io, Svgbob) that plug directly into the engine.

## Installation

```bash
# uv (recommended for isolated CLI installs)
uv tool install texsmith

# pip / pipx
pip install texsmith
pipx install texsmith
```

TeXSmith targets Python 3.10+ and expects a LaTeX distribution (TeX Live, MiKTeX, or MacTeX) when you pass `--build`. Optional converters such as Mermaid rely on Docker (`minlag/mermaid-cli`) unless you register custom handlers.

### Platform notes

- **Linux** – Install TeX Live (full) via your package manager or `install-tl`. When running inside CI containers, cache `~/.texliveYY` so repeated latexmk runs stay fast—or use the default Tectonic engine to minimise setup.
- **macOS** – Use [MacTeX](https://www.tug.org/mactex/) or `BasicTeX` plus the tlmgr packages reported by `texsmith --template <name> --template-info`. Homebrew’s `mactex` cask works well when paired with `uv`.
- **Windows** – TeXSmith runs via native Python or WSL. For PDF builds we recommend [MiKTeX](https://miktex.org/) + PowerShell, or WSL2 with TeX Live and Docker Desktop (needed for Mermaid).
- **Docker workflows** – Run `texsmith --build` inside a TeX Live container, mounting your project plus the template directory. Copy tlmgr prerequisites from `--template-info` so images compile without network access.

See the [Getting Started guide](docs/guide/getting-started.md) for a step-by-step walkthrough, verification commands, and Python API examples.

## Documentation

Browse the full documentation at [yves-chevallier.github.io/texsmith](https://yves-chevallier.github.io/texsmith) for:

- [Getting Started](docs/guide/getting-started.md): installation, prerequisites, and API snippets.
- [CLI Reference](docs/cli/index.md): every flag, including the template inspector.
- [Markdown Directory](docs/markdown/supported.md): exhaustive syntax coverage.
- [API Reference](docs/api/index.md): ConversionService, TemplateSession, handlers, and plugins.
- [Template Cookbook](docs/guide/template-cookbook.md): practical recipes for slots, overrides, packaging, and testing.
- [Release Notes & Compatibility](docs/guide/release-notes.md): TeXSmith feature history plus template/TeX Live requirements.

## Template catalog

Inspect templates by name or path to understand their slots, metadata attributes, TeX Live requirements, and declared assets:

```bash
texsmith --template article --template-info
# or inspect a local path
texsmith --template ./templates/nature --template-info
texsmith templates  # view discovery order across built-ins/packages/local/home
```

Use this command before wiring slots or when you need to confirm which tlmgr packages to preinstall in CI.

## Examples

The `examples/` directory includes reproducible demos:

- `examples/paper` – end-to-end render with bibliographies and latexmk (or Tectonic with `--engine tectonic`).
- `examples/diagrams` – Mermaid and Draw.io conversions.
- `examples/markdown` – exhaustive Markdown showcase with diagram/front-matter overrides.

Each example ships build instructions inside [`docs/examples/index.md`](docs/examples/index.md).

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
- Fragments use a `BaseFragment` + config dataclass model (`fragment = YourFragment()` export referenced by `fragment.toml` entrypoints). No legacy factories remain.

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
