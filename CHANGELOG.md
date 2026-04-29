# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `bibliography_show_urls` front-matter flag (default `false`) for the `ts-bibliography` fragment. When `false` (the new default), the `biblatex` preamble suppresses raw `url`/`urldate` field output and turns the entry's title into a `\href{<url>}{…}` hyperlink, preserving the underlying style's italic (`\mkbibemph`) or quoted (`\mkbibquote`) formatting. Long URLs no longer leak into justified two-column bibliographies as `\url{…}` chunks that produce streams of `Underfull/Overfull \hbox` warnings; the title stays clickable in the PDF. Set `bibliography_show_urls: true` in the document front matter to restore the previous behaviour and print the full URL inline (with the same hyphenation caveats as before).
- Structured `version:` front-matter schema (validated by Pydantic) that supersedes the previous string-only contract. Five shapes are accepted: free-form text (`version: "Draft 3"`), a list of integers (`version: [2, 3, 0]` → `"2.3.0"`), an explicit semver mapping (`version: {major: 2, minor: 3, patch: 0, pre: "rc1", build: "abc"}` → `"2.3.0-rc1+abc"`), a git derivation (`version: {git: true}` → `git describe --tags --dirty`), and a git-with-suffix variant (`version: {git: true, suffix: "(draft)"}` → `"v0.5.1 (draft)"`). The literal `version: git` shorthand is preserved as a backwards-compatible alias for `{git: true}`. Resolution lives in a new `texsmith.core.document_version` module (`format_version`, `FreeFormVersion`, `SemverListVersion`, `SemverDictVersion`, `GitVersion`, `DocumentVersionError`); the article template feeds the resolved canonical text through `escape_latex_chars` before injection, so structured shapes survive the metadata pipeline untouched (`type = "any"` on the manifest attribute) and validation errors surface as `DocumentVersionError` with the originating Pydantic message.
- Structured `date:` front-matter schema with three magic keywords on top of free-form ISO and string values: `date: today` renders today's system date in long form, `date: commit` renders the date of the last `HEAD` commit (via the new `git_commit_date()` helper in `texsmith.core.git_version`), and `date: none` (the new default when `date` is omitted) emits a bare `\date{}` so `\maketitle` drops the date line. ISO strings (`"2026-03-05"`) and YAML-parsed `date` objects render as long form localised by the document `language` (`"5 mars 2026"` for `language: french`, `"March 5, 2026"` for English; first of the month becomes `"1er"` in French). Resolution lives in a new `texsmith.core.document_date` module (`format_date`); the article template's manifest attribute is `type = "any"` so structured shapes pass through, and `core.metadata` now skips string coercion for structured `date` values during press-metadata flattening.
- `texsmith.core.git_version.git_commit_date()` returns the committer date of `HEAD` (using `git log -1 --format=%cs`) for the repository containing the supplied path, with a per-repo cache and the same warn-on-missing semantics as `git_describe()`. Used by the `date: commit` keyword.
- `article` template `version` front-matter field that surfaces in `\maketitle` underneath the date in a `\small` style. The value is free-form (`version: "Consolidation du draft de janvier 2026"`) or the literal sentinel `version: git`, in which case the template runs `git describe --tags --dirty` against the document's repository (with a 7-character commit-hash fallback, suffixed `-dirty` when the worktree has uncommitted changes) and emits a warning if no git metadata is reachable. The resolver lives in a new `texsmith.core.git_version` module — `git_describe()`, `git_commit_date()`, `resolve_git_root()`, `reset_cache()` — so other templates can opt in. Tag names containing LaTeX-special characters (`_`, `&`, `%`, `#`, …) are escaped by the article template before being injected, so a tag like `v1.0_alpha` renders correctly.
- New `invisible_chars` Markdown extension (registered by default) that replaces stray zero-width characters — ZWSP (`U+200B`), ZWNJ (`U+200C`), ZWJ (`U+200D`), and BOM (`U+FEFF`) — with a non-breaking space (`U+00A0`) in text nodes. Code, `pre`, `kbd`, `script`, and `style` elements are left untouched, so deliberate zero-width sequences inside fenced code blocks still survive. Defends against pasted content silently smuggling glyphs that small-caps fonts (e.g. `lmromancaps10-regular`) cannot render.
- `yaml table` columns can now omit the `name` field. When every column omits it, the rendered output drops the `<thead>` (and the corresponding LaTeX `\midrule` after the header) so the body sits directly under `\toprule` — handy for two-column key/value summaries. Mixed cases (some named, some not) keep the header row and emit blank `<th>` cells for the unnamed columns. Per-column `align`, `width`, and `width-group` keep their usual meaning. The `examples/tables/tables.md` tutorial gains a "Headerless tables" section showcasing the feature.
- Plain Markdown tables now support inline horizontal separators: any body row whose every cell is just three or more dashes (`| --- | ----- | --- |`, surrounding whitespace allowed) is rewritten as a separator row tagged with `data-ts-role="separator"` (a single `<td colspan="N">`) and rendered as a bare `\midrule` in LaTeX. A new `_MarkdownTableSeparatorTreeprocessor` performs the rewrite on `<tbody>` / `<tfoot>` rows and reuses the same separator markup that `yaml table` emits, so both the legacy `render_tables` handler and `render_yaml_table` (when bound via `yaml table-config`) handle the rule uniformly. Cells with fewer than three dashes, or rows where any cell carries non-dash content, are left as regular data rows.

### Changed

- Standalone short-bold paragraphs are now promoted to a `\tslead{…}` lead-in instead of rendering as bare `\textbf{…}`. A `<p>` whose only meaningful child is a single `<strong>` element with under 80 characters of plain text triggers the rule; bold inside running prose, bold over the threshold, and bold labels synthesised by other extensions (e.g. `tabbed-set` labels nested in a `<div>`) keep the original `\textbf{…}` rendering. The macro — `\providecommand{\tslead}[1]{\par\noindent\textbf{#1}\par\nobreak\smallskip}` — is emitted idempotently next to every use (same pattern as `\texsmithHighlight`), so it can be overridden in a custom preamble snippet without touching the converter. Motivation: under `babel-french` (and any class with a non-zero `\parindent`), a bold pseudo-heading wedged between two block environments (`\end{center}` … `\textbf{Méthodologie}` … `\begin{center}`) renders flush left while the same construct after running prose is indented; `\tslead` forces a stable `\noindent` paragraph break + `\smallskip` so both cases align without authors having to sprinkle manual `\noindent`s. Implemented as a new PRE-phase `<p>` handler (`render_lone_bold_paragraph`) and a new `lead.tex` partial; documented under "Standalone bold paragraphs" in `docs/syntax/formatting.md`.
- The article template now emits `\date{}` (no date line) when no `date` is configured, replacing the previous `\date{\today}` fallback. Documents that want today's date must opt in explicitly with `date: today`. Same applies when `date: none` is set explicitly.
- The article template's title block emits a `\date{{\small <version>}}` block when only a version is set (no date), instead of suppressing the version entirely. Combined date+version blocks are unchanged.
- `texsmith.core.git_version.format_version` is now a thin shim that forwards to `texsmith.core.document_version.format_version`. The shim is preserved for backwards compatibility; new code should import from the new module.
- `ts-extra` margin-note safety buffer (`\tsmarginparbuf`, subtracted from the available outer margin when clamping `\marginparwidth`) bumped from `6pt` (~2 mm) to `6mm`, so margin notes typeset via the `{margin}[…]` extension keep a visibly safe gap to the page edge instead of sitting 2-3 mm away. Documents that need the previous, tighter clamp can override it in a custom preamble snippet (`\setlength{\tsmarginparbuf}{6pt}`).

### Fixed

- The `footnote` LaTeX partial no longer emits a trailing `%` after the closing brace. Inline footnotes followed by text on the same source line (e.g. `…enseignants[^note] ; suite`) used to render as `\footnote{…}% ; suite`, where the stray `%` silently commented out the rest of the rendered paragraph; the closing brace is now bare so subsequent inline content is preserved.
- Inline `<code>` inside a footnote definition now reaches the LaTeX formatter and is rendered as `\texttt{…}` (with `_`/`#`/`%` escaped) instead of being flattened to raw text. The footnote handler now runs the same rich-text preparation that lists and definition lists already use before extracting the body, so a footnote like ``[^note]: La source `EPFL_REORIENT` documente …`` produces `\texttt{EPFL\_REORIENT}` and no longer trips XeLaTeX with `Missing $ inserted` on the unescaped underscore.
- `article` template now loads `morewrites` first thing after `\documentclass`, virtualising `\newwrite` so XeLaTeX's hard 16-register limit no longer truncates documents that combine many glossary groups (each group costs one `\write`) with biblatex, hyperref's outline, the toc, and `listoftables` / `listoffigures`. Before this change a typical front matter with 5+ glossary groups and `listoftables: true` failed at runtime with `! No room for a new \write` at `\listoftables`, and `tectonic` produced a silently truncated PDF that stopped before the back matter (LOT, glossaries, bibliography). `morewrites` is loaded ahead of `xcolor` so subsequent allocations route through its virtual stream pool. Added to `tlmgr_packages` so non-tectonic builds resolve it automatically.
- `ts-fonts` now activates `U+200B` and maps it to `\hskip\z@`, mirroring the existing `U+2135` (Aleph) precedent. `biblatex`'s `blx-unicode.def` workaround for [biblatex#979](https://github.com/plk/biblatex/issues/979) appends a literal ZWSP inside `\textnohyphenation`, which `babel-french` invokes from its redefinition of `\mkbibnamefamily`; rendered through the active small-caps font that lacks a glyph for `U+200B`, this used to spam `Missing character: There is no ​ (U+200B) in font [lmromancaps10-regular.otf]` warnings on every French-language bibliography. `ts-fonts` is loaded before `biblatex` in every bundled template, so `blx-unicode.def` reads the literal ZWSP under the new active catcode and the resulting macro expands to a zero-width breakable skip — preserving the line-break-opportunity semantics the workaround was after, without ever hitting the font.

## [0.3.0] - 2026-06-25

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

- Two long-standing test assertions that had drifted away from the templates they exercise: `test_render_template_applies_markdown_metadata` expected the title/subtitle pair `\\\large` (pre-spacing format) but the article template now emits `\\[0.5em]\large` (commit `c9aff0f`); `test_article_template_supports_columns_option` expected the `twocolumn` documentclass option, but the article template intentionally omits it and uses `\twocolumn[…]` after `\maketitle` so `\@thanks` stays populated and affiliation footnotes survive (`\tsreplayfn` flushes them). Both assertions updated to match the current — correct — template behaviour.
- Python 3.10 compatibility regression: `enum.StrEnum` is 3.11+, but `requires-python = ">=3.10"` and the CI matrix exercises 3.10. The `tables` extension imported `StrEnum` unconditionally, breaking 50 test files at collection time on 3.10 (every test that transitively touches the markdown processor). Added a tiny version-guarded shim that subclasses `str, Enum` on 3.10 and re-exports the stdlib class on 3.11+. Aligned `ruff target-version` with `requires-python` so the version guard isn't flagged as `UP036 outdated version block`.
- Page-number prefix (`n1` / `n2`) leaking into grouped acronym tables produced by the `glossaries` package. Two-part fix: (1) bumped the `pyxindy` dependency to **0.0.7**, which routes every `markup-locref` slot (`:open` / `:close` / `:sep` / `:prefix`) through the existing `_normalize_markup_string` helper so the xindy `~n` newline escape no longer leaks into the rendered output (`_update_locfmt` previously copied the raw strings verbatim); (2) extended TeXSmith's defensive post-processor (`adapters/latex/engines/__init__.py`) to glob `*-gls` in addition to `*.gls` so files emitted by `\newglossary*{<type>}` (e.g. `glossary.technical-gls`) go through `sanitize_glossary_output` for users still on pyxindy <0.0.7.
- Glossary page numbers were not clickable: the `glossaries` package only wraps numbers in `\hyperpage` when `hyperref` is loaded *before* it. Both the `article` and `book` templates now load `babel` and `hyperref` before `\VAR{extra_packages}` (which carries `glossaries` via `ts-glossary`), enabling both babel-localised acronym titles and hyperref-backed clickable backreferences. Same constraint that applies to babel localisation, made explicit in the preamble comments.
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
