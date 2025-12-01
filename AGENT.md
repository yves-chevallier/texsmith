# TeXSmith Agent Guide

## Architecture Overview

- Flow: `texsmith.ui.cli` (Typer) and library calls both funnel into `api.ConversionService`, which splits inputs/front matter/bibliography, prepares `Document` objects, and drives the render pipeline.
- Document model: `api.document.Document` stores normalised HTML + front matter + slot directives; `DocumentRenderOptions` controls heading offsets/numbering/title handling; slot selectors merge CLI/front matter values.
- Render engine: `core.conversion` builds `RenderContext/DocumentContext`, then runs `adapters.handlers` in `RenderPhase` order (PRE/BLOCK/INLINE/POST) to rewrite the BeautifulSoup tree, emit LaTeX fragments, and register assets; asset hashing/manifests live in `_assets`.
- Templates: `core.templates` + `api.templates` load template runtimes, slots, bindings, and overrides; `TemplateSession`/`TemplateRenderer` assemble slot bundles and LaTeX scaffolding; template language resolution supports builtins and user paths.
- Fragments: `core.fragments` orchestrates fragment metadata/injection; builtin fragments under `fragments/*` (ts-geometry, ts-typesetting, ts-fonts, ts-extra, ts-keystrokes, ts-callouts, ts-code, ts-glossary, ts-index, ts-bibliography, ts-todolist) populate template slots.
- Engines: `adapters.latex.engines` resolves Tectonic/latexmk (plus biber makeindex helpers), builds command/env args, and can run via Docker when configured; formatter/pygments handle LaTeX-safe code blocks.
- Extensions/plugins: `adapters.plugins` (Material/snippet) and `extensions` (progress bar, texlogos, index helpers) extend Markdown parsing or LaTeX output; `adapters.transformers` hosts diagram converters (mermaid/drawio), strategies, and helpers.
- Assets/fonts: `fonts` caches/embed OpenMoji/Noto; asset registry ensures template and diagram assets are copied or hashed when `copy_assets`/`convert_assets`/`hash_assets` flags are set.

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

## Working agreements

- Always run `uv run pytest` after modifying Python code.
- Follow coding principles: SOLID, YAGNI, SSOT, KISS and design principles.
- Always run `uv run ruff format .` and `uv run ruff check .` after changing Python files.
- Maintain clear and concise documentation for all features added or modified.
- Use type hints for all functions and methods.
- Write unit tests for new features and bug fixes.
