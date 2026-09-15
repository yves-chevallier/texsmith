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

TeXSmith is a [Python](https://www.python.org/) package and CLI tool to convert **Markdown** or **HTML** documents into **LaTeX** or **Typst**. It is designed to be extensible via templates and integrates with [MkDocs](https://www.mkdocs.org/) for generating printable documents from documentation sites.

<p align="center">
<!-- Absolute link for compatibility with PyPi -->
<img src="https://raw.githubusercontent.com/yves-chevallier/texsmith/master/docs/assets/ts-logo.svg" width="70%" />
</p>

## TL;DR

```bash
pip install texsmith
texsmith input.md input.bib -o build/ --build
```

Check the installed version with `texsmith --version` or in Python with `texsmith.get_version()`.

## Key features

- **TMark Markdown** – The [TMark](https://github.com/yves-chevallier/tmark) parser reads every Markdown source, so callouts, containers, data tables, counters and cross-references mean the same thing in the editor, on the site and in the PDF.
- **Typed IR with multiple backends** – Documents are parsed into a typed intermediate representation, run through TeXSmith's IR passes, resolved, and emitted as **LaTeX** (default) or **Typst** (experimental) via `--format`.
- **Template-first runtime** – Bundle multiple fragments into slots, merge front matter metadata, and emit LaTeX projects ready for Tectonic or latexmk with Docker-friendly manifests.
- **CLI and Python parity** – The Typer-powered CLI wraps the same ConversionService you can consume as a library, making CI/CD and notebooks behave like local runs.
- **Actionable diagnostics** – Every finding, from the Rust parser or from TeXSmith, prints in one shape with a stable code. `--strict` refuses to build a PDF from a document that has one, `--diagnostics-json` hands the lot to an editor or CI, and `--deprecated` keeps 0.6 spellings from failing a strict run while you migrate.
- **Extensible converters** – Add IR passes, redefine a construct's contract macro in a fragment or template, or ship diagram transformers (Mermaid, Draw.io, Svgbob) that plug directly into the pipeline.

## Installation

```bash
# uv (recommended for isolated CLI installs)
uv tool install texsmith

# pip / pipx
pip install texsmith
pipx install texsmith
```

TeXSmith targets Python 3.10+ and expects a LaTeX distribution (TeX Live, MiKTeX, or MacTeX) when you pass `--build` with the default LaTeX backend. Optional converters such as Mermaid try a Playwright exporter first, then a local CLI, then Docker (`minlag/mermaid-cli`); `--diagrams-backend` pins one, and you can register your own with `texsmith.adapters.transformers.register_converter`.

To build with the **Typst** backend (`--format typst`), install the embedded compiler as an extra:

```bash
pip install "texsmith[typst]"
# or with uv
uv tool install "texsmith[typst]"
```

This bundles the `typst` PyPI package, so no system binary is required. A system `typst` on `PATH` (Homebrew, `cargo install typst-cli`, or a GitHub release) is detected automatically as a fallback. See the [Output backends guide](docs/guide/plumbing/backends.md) for details.

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
- [Syntax](docs/syntax/index.md): the TMark dialect, construct by construct.
- [Migrating to TMark](docs/guide/migration.md): what changed since 0.6 and what `tmark lint --fix` rewrites.
- [API Reference](docs/api/index.md): ConversionService, TemplateSession, IR passes, and plugins.
- [Template Cookbook](docs/guide/templates/template-cookbook.md): practical recipes for slots, contract macros, packaging, and testing.
- [Diagnostics](docs/guide/diagnostics.md): the finding format, `--strict`, `--deprecated`, `--diagnostics-json`.
- [Release Notes](docs/about/release-notes.md): TeXSmith feature history plus template/TeX Live requirements.

## Template catalog

Inspect templates by name or path to understand their slots, metadata attributes, TeX Live requirements, and declared assets:

```bash
texsmith --list-templates                        # discovery order: built-ins, packages, local, home
texsmith --template article --template-info      # one template's slots, attributes, tlmgr packages
texsmith --template ./templates/nature --template-info   # or a local path
texsmith --template article --template-scaffold ./templates/mine   # copy one to edit
```

Use this command before wiring slots or when you need to confirm which tlmgr packages to preinstall in CI.

## Examples

The `examples/` directory includes reproducible demos:

- `examples/paper` – end-to-end render with bibliographies and latexmk (or Tectonic with `--engine tectonic`).
- `examples/diagrams` – Mermaid and Draw.io conversions.
- `examples/tmark` – the TMark syntax construct by construct, with diagram/front-matter overrides.

Each example ships build instructions inside [`docs/examples/index.md`](docs/examples/index.md).

## Project layout

```text
src/texsmith/
├── readers/      tmark.parse — the one reader
├── ir/           the generated Python mirror of tmark's IR schema, plus walkers
├── passes/       the IR passes (include, glossary, var, title, snippet, assets,
│                 doi, emoji, scripts | slots, headings, highlight)
├── writers/      what stays Python-side of the writers: escaping, asset naming,
│                 the Typst document wrapper
├── diagnostics/  the one diagnostic shape, its codes, the sink and file table
├── templates/    the built-in templates (article, book, letter, snippet)
├── fragments/    the ts-* fragments that define the contract macros
├── core/         conversion orchestration, documents, bibliography, templates
├── adapters/     LaTeX engines, diagram transformers, Docker, MkDocs plugins
└── ui/cli/       the Typer CLI
```

The MkDocs companion is a separate workspace package, `packages/mkdocs_texsmith`.

## Core architecture highlights

- `ConversionService` is the single orchestrator behind both the CLI and the library. Provide a `ConversionRequest`, get a `ConversionResponse` carrying either a `ConversionBundle` or a `TemplateRenderResult`.
- A construct is rendered by a **contract macro** a `ts-*` fragment provides, not by a template-side partial. The writer names the fragment it needs in `Requires.fragments`, so activation is by construction; redefining the macro is how a template restyles the construct.
- `TemplateRenderer` owns slot aggregation and LaTeX assembly. `TemplateSession` focuses on session state, template options, and bibliography tracking.
- Slot directives from front matter, CLI flags, and programmatic overrides converge on one data model, so every entry point behaves the same.
- Every finding — from tmark or from TeXSmith — is one `Diagnostic` in one shape, gated by `--strict` and dumped by `--diagnostics-json`. `DiagnosticEmitter` decides where they are shown (CLI uses `CliEmitter`; libraries can plug in their own).
- Fragments use a `BaseFragment` + config dataclass model (`fragment = YourFragment()` export referenced by `fragment.toml` entrypoints). No legacy factories remain.

### Programmatic conversions with `ConversionService`

```python
from pathlib import Path

from texsmith import ConversionRequest, ConversionService

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
for record in response.documents[0].diagnostics:
    print(record.severity, record.code, record.message)
```

If you only need a quick conversion, the high-level helpers (`texsmith.Document`, `texsmith.convert_documents`, `texsmith.TemplateSession`) continue to work, but they now reuse the same ConversionService plumbing as the CLI.

> Upgrading from 0.6? [Migrating to TMark](docs/guide/migration.md) lists every changed spelling and what `tmark lint --fix` rewrites; `CHANGELOG.md` has the release history.

## Render pipeline

TeXSmith parses every document into a typed intermediate representation (IR)
and then emits a backend from that IR:

```
tmark.parse → IR → TeXSmith passes → tmark.resolve → tmark.write → LaTeX | Typst
```

- **Readers** produce the IR: `tmark.parse` for a Markdown source, and the
  one reader; an input is a Markdown source.
- **IR** (`texsmith.ir.model`) is a typed, backend-neutral node tree generated
  from tmark's committed schema. Semantic hints travel as `Span`/`Div`
  attributes rather than backend strings.
- **Passes** (`texsmith.passes`) are pure `Document → Document` functions doing
  the work a writer cannot: includes, assets and diagrams, DOI lookups,
  moustaches, snippets, slots, headings, font scripts, glossary entries.
- **Writers** are tmark's. Each construct is emitted as a fixed macro or
  environment, and the fragment named in `Requires.fragments` defines it —
  redefining that macro is how a template overrides a construct's look.

Resolution happens **once**, over the whole document, so numbering and
cross-references are consistent across slots. `--numbering tmark` moves the
numbers of figures, tables, listings, equations and sections into that single
resolve, making the `.tex` and the `.typ` print identical numbers.

Select the backend with `--format {latex,typst}`. See the
[Output backends guide](docs/guide/plumbing/backends.md), the
[pipeline walkthrough](docs/guide/plumbing/pipeline.md) and the
[IR passes & fragment contracts reference](docs/api/handlers.md).
