# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Structured `glossary:` front-matter section, validated with pydantic, that complements the existing `*[KEY]: …` body syntax. Each entry carries an explicit `description` and an optional `group`; groups are declared at the top with their displayed title (`groups: {tech: Acronymes techniques, …}`), and entries with no group fall back to the standard acronym table. TeXSmith emits one localised `\printglossary[type=<group>, title=<title>]` per group in declaration order, plus `\printglossary[type=\acronymtype]` for ungrouped entries; the default acronym title now uses `\acronymname` so `babel` localises it (e.g. *Acronymes* under `language: french`). Front-matter entries that never appear in the body are still defined in the glossary; entries that do appear are auto-substituted with `\acrshort{KEY}` whenever the strict, case-sensitive form occurs in the text — `\Gls`/`\GLS` casing helpers are not synthesised (a documented limitation). The `article` template now loads `babel` before `extra_packages` so the `glossaries` package picks up the active language. New `examples/glossary/` tutorial.
- `article` template now supports `listoffigures: true` and `listoftables: true` front-matter flags (mirroring the `book` template), plus a `lists_position: toc | backmatter` knob to choose whether the lists are inserted right after the table of contents (default) or just before the backmatter and references. Each list is wrapped in `\ifnum\value{figure|table}>0` so empty documents don't emit blank pages.
- New `yaml table` Markdown fence describing complex tables in YAML and compiling to `tabular` / `tabularx` / `longtable` on demand. Supports multi-row and multi-column cells (in headers and body), nested grouped headers, width-groups, separators with optional labels, footers, captions via the standard `Table: …` syntax, and explicit width control. Validation errors surface as inline error admonitions with a clear, localised message. New `examples/tables/` tutorial pairs each YAML source with its rendered output and ships a Makefile to build the demo PDF.
- `ts-extra` now auto-loads the `multirow` package when `\multirow` is detected in the rendered LaTeX.
- `Table: <caption> {#label}` now also works on plain Markdown tables: a tree processor pairs the caption paragraph with the following `<table>` and injects a `<caption>` child carrying the caption text (and optional `id` from the `{#label}` part). Both the yaml-table renderer and the legacy table renderer consume `<caption>` directly, so the LaTeX output gets a proper `\caption{…}` with its `\label{…}`.
- 0.5 em of vertical breathing room is inserted between the caption and the table body for both yaml-tables and plain Markdown tables when a caption is present.
- New `yaml table-config` fence applied right below a plain Markdown table sends per-column attributes (`align`, `width`, `width-group`) and table-level settings to the yaml-table renderer. Marks the table with `data-ts-*` attributes so it goes through the same `tabular` / `tabularx` / `longtable` selection as full yaml-tables, including caption handling. A `BlockProcessor` parses the fence into a real ElementTree marker so a sibling tree processor can bind the config to the preceding `<table>`.
- New explicit `width: X` value (case-insensitive, alias for `tabularx`'s `X` column) marks a single column as flexible without needing a `width-group` shim. When any column carries `width: X`, only that column expands; the others keep their natural width.
- `align` accepts long forms (`left`, `right`, `center`, `centre`, `justify`, `justified`) in addition to the short single-letter forms; both are normalised to the short form internally.
- New `{margin}[note]{side?}` inline shorthand for margin notes, joining the unified `{keyword}[content]` family (alongside `{index}[term]` and `{latex}[payload]`). The optional single-letter suffix picks a side — `l` / `i` force the left margin (scoped `\reversemarginpar`), `r` / `o` the right; without a suffix the note follows the document's default (right in `oneside`, outer in `twoside`). Inline markdown inside the note is preserved (bold, italic, code, links). Compiles to `\marginnote{…}` from the LaTeX `marginnote` package, which `ts-extra` now auto-loads on detection. Three defensive layers keep notes within the page on any geometry: (1) `\marginfont` is configured with `\footnotesize`, `\sloppy`, `\emergencystretch=1em` and lowered hyphenation penalties so long words break (or inter-word spacing stretches) rather than overflow; (2) an `\AtBeginDocument` hook clamps `\marginparwidth` to the horizontal space the document's geometry actually reserves on each side (recto and, in twoside, verso), minus `\marginparsep` and a 6 pt safety buffer; (3) a custom `geometry: {left: 3cm, right: 4cm}` yields notes that still fit on both pages with no manual `marginparwidth=…` tweak. New `examples/marginnote/` tutorial with a Makefile; extension documented in `docs/syntax/notes.md`.

### Fixed

- HTML comments (`<!-- ... -->`) are now stripped before rendering and no longer appear verbatim in the LaTeX output. A shared `core.html_utils.strip_html_comments` helper runs in `extract_slot_fragments` (before node serialisation, where `str(comment_node)` would otherwise silently drop the `<!--`/`-->` delimiters and expose the raw comment text) and from the `discard_unwanted` PRE-phase handler.
- `tabularx` column specifications now use `>{\raggedright\arraybackslash}X`, `>{\raggedleft\arraybackslash}X`, and `>{\centering\arraybackslash}X` for all columns (including the first), replacing the previous `l`/`X` split. This prevents text overflow in two-column (`twocolumn`) document layouts and improves line-breaking throughout.
- Inline formatting (bold, italic, etc.) inside quoted text (`"**bold**"`) is now correctly rendered — `AtomicString` was preventing further inline processing inside `<q>` elements.
- Silent exception swallowing in post-render rule/asset collection now emits a diagnostic warning instead of discarding the error.
- Nested list environments (`\begin{itemize}`) no longer appear glued to the parent item text on the same line; a newline is now inserted between the item content and any nested `\begin{itemize|enumerate|description}`.
- Table caption numbering no longer skips numbers (e.g. 1, 2, 4, …). `ts-extra` previously auto-loaded `ltablex` under single-column layouts, which silently transformed every `tabularx` into a `longtable` internally and bumped the `table` counter twice per use. Replaced by a plain `tabularx` load; explicit `longtable` is still detected on demand.

### Changed

- Removed dead code after the early `return` in `_allow_hyphenation` (unreachable lines).
- Dropped the unused `fragments` field from `ExecutionContext`; fragment resolution was already propagated through `template_overrides`.
- Deduplicated `runtime_common.get("code")` lookups in `_render_slot_fragments` into a single local variable.
- Reverted an uncommitted injection of `template_overrides` into the Jinja render context (`runtime_common`) — it had no consumer and exposed internal state unnecessarily.
- **Tables extension refactor (SSOT).** Introduced `texsmith.extensions.tables.constants` housing `TableAttr` (StrEnum for every `data-ts-*` attribute), `PERCENT_RE`, `ALIGN_ALIASES` / `ALIGN_WRAPPERS`, and a `Priority` class that documents each pipeline position. Removed the duplicate `_PERCENT_RE` in `layout.py`. Collapsed the three identical align/width/width-group validator triplets (`LeafColumn`, `ColumnGroup`, `ColumnConfig`) into a shared `_ColumnAttrs` base. Extracted a single `_consume_fence` helper used by both preprocessors and the block processor; the two preprocessors now fail identically (admonition surfaced on parse error) instead of diverging between silent fall-through and block-level error emission. Caption handling no longer wraps the table in a throwaway `<figure>` / `<figcaption>` to be unwrapped by `render_figures`; the `<caption>` is injected directly into the `<table>`. `render_figures` keeps its figure-with-table path (still reached by `pymdownx.blocks.caption`) and routes via a new `is_texsmith_table()` helper instead of literal attribute comparison. The `build_error_element` helper in `tables.html` lets the preprocessor and the block processor share admonition construction.
- **`slot_options` plumbing simplified.** The per-slot render flags (`SlotOptions`) now live only on `Document` and are read directly by the consumer (`extract_slot_fragments`) instead of being copied through `ExecutionContext` and `BinderContext`. The `parse_slot_mapping_with_options` and `extract_front_matter_slots_with_options` wrappers were removed; `parse_slot_mapping` and `extract_front_matter_slots` now always return a `(selectors, options)` tuple.
- **Fragment resolution extracted.** New `core.fragments.resolution` module with a typed `FragmentModifiers(append, prepend, disable)` dataclass, `parse_modifiers(raw)` for front-matter shapes, and a pure `merge_fragments(defaults, override, *, cli_enable, cli_disable)` function. `_resolve_fragments_list` is now a 15-line orchestrator instead of a 65-line dispatcher with three nested helpers.
- **Silent `except Exception` handlers documented or warned.** Font-fallback scans in `conversion/renderer.py` now emit a warning via the diagnostic emitter on failure; user-supplied `should_render` callbacks in `core/fragments` warn with the fragment name instead of silently swallowing the failure; the third-party template-distribution discovery in `templates/loader.py` keeps its broad catch but carries an explicit comment and `# noqa: BLE001` explaining why it is intentional.

### Removed

- **`ExecutionContext` and `BinderContext` merged into `ConversionContext`.** Both classes carried an almost identical set of fields resolved at two successive stages (pre- and post-template-binding); they were collapsed into a single `core.conversion_contexts.ConversionContext` with optional `config` / `template_binding` fields that become populated when `bind_template` runs. Dead fields dropped: `BinderContext.documents: list[Document]` (only ever appended, never read meaningfully), `BinderContext.bound_segments` (written in `_render_document`, never read). The file `core/execution.py` has been deleted.

- **Function renames tracking the new context class:**
  - `resolve_execution_context` → `resolve_conversion_context` (returns the partially-populated `ConversionContext`).
  - `build_binder_context` → `bind_template` (mutates the context in place to populate `config`, `template_binding`, and the template-refined `slot_requests`; same object returned for chaining). Its keyword parameter `execution=` is renamed to `context=`.
  - `ConversionResult.binder_context` field renamed to `ConversionResult.context`.

## [0.2.2] - 2026-02-24

### Added

- CLI/API version reporting (`texsmith --version`, `get_version()`).
- Configurable HTTP user agent for remote asset and emoji fetching (`--http-user-agent` / `TEXSMITH_HTTP_USER_AGENT`).
- TLS download helper with cert guidance for network fetches.
- Cached Wikipedia images for the book example under `.wiki/` with documentation.

### Changed

- Horizontal rules now force a page break in LaTeX output.
- Asset summaries hide temporary build roots and `.converted` cache files.
- Letter example no longer hard-codes the format, allowing snippet overrides; docs include local build steps.
- Book example images now resolve via raw GitHub URLs to avoid third‑party rate limits.
- CI now runs `apt-get update` before installing system dependencies.

### Fixed

- Playwright SVG conversion now handles `viewBox`-only SVGs to prevent blank PDFs.
- Suppressed noisy Tectonic `lineno` UTF‑8 warnings and made console output encoding-safe.
- XeTeX fallback transitions no longer leak across scripts; arrow glyphs prefer Noto Sans Symbols.
- Convert common Unicode symbols to LaTeX math macros to avoid missing glyphs.

## [0.1.0] - 2025-12-20

### Added

- Initial TeXSmith CLI for Markdown to LaTeX/PDF conversion, including multi-document rendering and slot-aware templates.
- Template system with built-in article/book/letter/snippet variants plus user template discovery and overrides.
- Fragment system for typography, geometry, fonts, glossary/index, code blocks, and callouts.
- Extensions for bibliography/citations, acronyms, mermaid/drawio diagrams, and rich admonitions.
- Asset pipeline for fonts/emoji, hashed assets, and download helpers for Tectonic/Biber/PyXindy.
- Documentation and examples (`docs/`, `mkdocs.yml`, `examples/`) plus developer docs and scripts (`README.md`, `DEVEL.md`, `scripts/`).
- Tooling and quality gates (`pyproject.toml`, `noxfile.py`, `Makefile`, tests, CI, coverage, ruff/pyright configs).

### Changed

- Renamed the project to TeXSmith and refactored the codebase into `src/texsmith` with a `texsmith.core` conversion pipeline.
- Reworked bibliography handling, front matter parsing, slot injection, and template rendering orchestration.
- Switched the default LaTeX engine to Tectonic and improved typography, headings, and smart punctuation defaults.

### Fixed

- Numerous issues across templates (article/book), MkDocs output, snippets, CI, and Windows compatibility.

### History

- 2025-10-18: Seeded the initial LaTeX renderer and template set under `latex/`.
- 2025-10-19: Added performance instrumentation and the first `docs/` content.
- 2025-10-20: CLI accepted Markdown input, introduced article templates, examples, and a `build` command.
- 2025-10-21: Added render phases, acronyms/index extensions, and renamed the project to TeXSmith.
- 2025-10-23: Added the EPFL thesis template, `LICENSE.md`, `DEVEL.md`, and multi-document CLI support.
- 2025-10-27: Major refactor around `texsmith.core`, `ConversionService`, diagnostics, and regression tests.
- 2025-11-16: Added the mermaid extension and expanded built-in templates and docs.
- 2025-11-24: Introduced rule/slot validation diagnostics and refined fragment registry behavior.
- 2025-11-27: Made Tectonic the default engine and added download helpers/Makefiles for fonts and tools.
- 2025-12-01: Added diagram generation via Playwright and `ts-typesetting` fragments.
- 2025-12-11: Polished CLI options, snippets, and CI pipelines leading up to the release tag.
