# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Nothing yet.

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
