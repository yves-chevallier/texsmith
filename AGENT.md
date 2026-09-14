# TeXSmith Agent Guide

## Architecture Overview

TeXSmith converts a document by handing the language to the `tmark` Rust core
and keeping for itself everything that needs a filesystem, a network, a process
or a template decision.

```text
tmark.parse ─▶ IR ─▶ pre passes ─▶ tmark.resolve ─▶ post passes ─▶ tmark.write ─▶ Body
```

- **Entry points**: `texsmith.ui.cli` (Typer, one root command) and library calls
  both funnel into `core.conversion.service.ConversionService`, which splits
  inputs/front matter/bibliography, prepares `Document` objects and drives the
  render. `packages/mkdocs_texsmith` is the MkDocs companion — **one** plugin,
  `texsmith`; `texsmith.counters` and `texsmith.index` are deprecation aliases
  that warn and do nothing.
- **Readers** (`readers/`): `tmark.parse` for every Markdown source; the
  only reader: a source is Markdown, and `tmark.parse` reads it. There is no
  `--reader` option and no HTML input.
- **IR** (`tmark.ir`): the document tree, imported from the tmark wheel, which
  generates and ships it (`tmark.ir.model` from the schema, plus `codec` and
  `walk`). TeXSmith keeps no mirror of its own: the schema is tmark's, so the
  Python mirror is too, and a field added to a node is no longer a change in
  two repositories. `Span` comes from there as well, and
  `texsmith.diagnostics` imports it rather than restating it.
- **Passes** (`passes/`): pure `(Document, PassContext) -> Document` functions.
  `pre` (before `tmark.resolve`) may add, remove or rewrite blocks; `post` only
  slices the block list or computes per-body options, so the `Resolved` of the
  whole document stays valid. `DEFAULT_PIPELINE` is the order; a pass registers
  a `PassSpec` with `after=` and `build_pipeline` sorts them stably. A pass
  never raises — a failure becomes a visible literal plus a diagnostic at the
  node's span.
- **Writers**: tmark's. Each construct is a fixed macro (`\ts<name>`) or
  environment (`ts<name>`), or a Typst function (`#ts-<name>`). `writers/` keeps
  only what has to stay Python-side: LaTeX and Typst escaping, asset naming, the
  standalone Typst document wrapper.
- **Fragments** (`fragments/`): a `ts-*` fragment *provides* the contract macros
  a writer can name (`specs/migration/fragment-contracts.md` §1 is the mapping).
  A body's `Requires.fragments` activates them — by construction, never by
  sniffing rendered LaTeX. `\tsrule` is a rule inside a container next to
  `\tsdivider` at the top level; `\tsacr` is `\acrshort`, the short form.
- **Templates** (`templates/`, `core/templates/`): `manifest.toml` declares
  `[latex.template]` and optionally `[typst.template]` — attributes (with owners
  and normalisers), slots, assets, tlmgr packages, and the template's own IR
  `passes`. `TemplateSession`/`TemplateRenderer` assemble slot bundles.
- **Diagnostics** (`diagnostics/`): one record shape, stable kebab-case codes,
  one sink. `--strict` (or `press.features.strict`) fails the run after the
  `.tex` is written and before the engine runs; `--deprecated {warning,info,off}`
  (or `press.diagnostics.deprecated`) sets the level of the two transition codes
  before that gate; `--diagnostics-json` dumps them all.
- **Engines** (`adapters/latex/engines`): Tectonic (default) and latexmk, plus
  biber/makeindex/xindy helpers; `writers/typst/build.py` drives the Typst
  compiler (embedded wheel first, system binary as fallback). The Typst body
  carries the `texsmith.typ` contract library inlined, and `mitex` is pinned at
  `0.2.7`.
- **Assets/fonts**: `adapters/transformers` hosts the diagram converters
  (mermaid, draw.io, svg) the `assets` pass drives; `fonts/` caches the Noto and
  OpenMoji lookups the `scripts` and `emoji` passes use.

## Design Principles

Always adhere to these principles:

- Composition over inheritance.
- Modules can inject, extend, and redefine functionality.
- Modules remain deterministic through topological ordering.
- Modules foster reusability and remixing.
- Modules cooperate through well-defined contracts.
- limit scope to demonstrated needs; keep public interfaces clear.
- **NEVER** add shims or temporary fixes; refactor instead.
- **NEVER** introduce technical debt; address issues immediately.
- **NEVER** duplicate code; abstract and reuse existing functionality.
- **NEVER** introduce compatibility layers; maintain a single, clear implementation.

## The TMark core

TeXSmith sits on the `tmark` Rust core (`vendor/tmark`, a checkout of
`~/tmark`): parser, IR, printer, registries, writers. The design notes are under
`specs/migration/`; `specs/tmark-migration.md` is the plan the migration
followed.

- The Python-Markdown pipeline is gone: no Markdown extensions, no Python
  writers, no hand-written IR, no Jinja partials. New syntax goes through the
  TMark spec and parser, never through a Python shim.
- `templates/common/texsmith.typ` and the tmark crate's own copy of it are two
  copies of one contract; every function the writers call must exist in both
  with the same signature. `tests/test_fragment_contracts.py` checks TeXSmith's
  copy against what `tmark.fragments()` declares.

## Working agreements

- Always run `uv run pytest` after modifying Python code.
- Follow coding principles: SOLID, YAGNI, SSOT, KISS and design principles.
- Always run `uv run ruff format .` and `uv run ruff check .` after changing Python files.
- Maintain clear and concise documentation for all features added or modified.
- Use type hints for all functions and methods.
- Write unit tests for new features and bug fixes.

## Scripts

- `scripts/parity.py` is the regression gate over `tests/parity/corpus.yml` (the
  examples' command lines and every `docs/**/*.md` page). `baseline` records the
  normalised `.tex`/`.typ` of every entry under `tests/parity/baseline/`, which
  is **committed**; `baseline --check` re-renders and fails on any difference —
  there is no allow-list, so a difference is either a regression or a change its
  author re-records in a diff a reviewer reads. `--only GLOB` restricts it.
  `render --out DIR` dumps raw outputs; `pdf --baseline [--check]` compares built
  PDFs against `tests/parity/pdf-baseline.json`; `list` says which entries can
  run here. **Changing a page under `docs/` changes its baseline: re-record it.**
- `scripts/refresh_cli_help.sh` regenerates `docs/assets/cli-help`, the
  gitignored snippet `docs/cli/index.md` includes. Run it after touching a CLI
  option, before building the site.
