# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Created an explicit changelog to track the rewritten Git history.
- Documented the new fragment manifest (attributes + partials + required_partials), partial precedence (template > fragment > core), and conversion pipeline order.
- Expanded template discovery docs and CLI info output (slots, fragments, attribute columns).
- Marked the legacy ``texsmith.fragments`` import path as deprecated; fragments should rely on ``fragment.toml`` or entrypoint factories.
- Dropped unused template knobs (article twocolumn/preamble hooks, letter callout_style stub) to align manifests with the refactored pipeline.

### Changed

- Updated every reference to the scientific paper demo so that it matches the
  renamed `examples/paper` directory used by the CLI tests and documentation.
- Template lookup now prefers built-ins, then `texsmith-template-*` packages/entry points, then cwd/parents, then `~/.texsmith/templates`; explicit paths still bypass discovery.
- Built-in template docs reflect appendix slot ordering and removal of legacy cover/twocolumn/backmatter/emoji attributes.

## [0.3.0] - 2025-11-17

### Added

- Imported the Carauma article template, EPFL thesis scaffolding, and the book
  template migration.
- Published the MkDocs site content together with lint rules for Markdown and
  prettier formatting of documentation.
- Introduced the MkDocs plugin workspace, PDF press kit example, and CI coverage
  reporting defaults.

### Changed

- Hardened the bibliography pipeline, slot handling, and document renderer to
  better support mermaid diagrams, smart typography, and press metadata.
- Expanded the builtin templates (article, book, letter) with fonts, abstract
  slots, syntax-highlighted code blocks, and typography refinements.

### Fixed

- Addressed numerous CLI issues (slot injection, latexmkrc, todolist/biber
  warnings) and ensured `pyproject.toml` references non-editable workspace
  installs.
- Resolved regressions in the book template migration and documentation builds.

## [0.2.0] - 2025-10-27

### Added

- Completed the six-step core refactor: `texsmith.core` now owns the conversion
  service, template orchestration, diagnostics emitters, and document slots.
- Added multi-document CLI rendering, pylatexenc integration, MkDocs example
  projects, and a comprehensive regression test suite (CLI, MkDocs, templates,
  extensions).
- Introduced additional LaTeX extensions (acronyms, index generation, texlogos,
  bibliography improvements) and shipped assets such as the TeXSmith logo,
  docker adapters, and draw.io support.

### Changed

- Reworked bibliography handling, latex adapters, utility modules, and template
  manifests to match the new orchestration pipeline.
- Migrated existing templates to the new structure, moved partials into package
  modules, and refreshed documentation with dark-mode assets.

### Fixed

- Numerous formatting, ruff, and CI fixes plus better caching/performance in the
  renderer, docker adapter, and media pipeline.

## [0.1.0] - 2025-10-21

### Added

- Initial TeXSmith CLI implementation with LaTeX adapters, slot-aware templates,
  bibliography/config helpers, and end-to-end article rendering examples.
- Early documentation, MkDocs integration, and helper scripts for generating the
  cheese/scientific paper demonstration.
