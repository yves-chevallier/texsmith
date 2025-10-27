# TeXSmith API Overview

The API reference is generated with **mkdocstrings** to stay in sync with the code base. This section is organised into themed pages so you can quickly locate the module you need.

Each page uses `::: module.path` directives; mkdocstrings resolves them at build time and renders docstrings, signatures, and cross-references.

## API Sections

[`high-level`](high-level.md)
: High-level orchestration helpers (`texsmith.api`) for programmatic conversions and template sessions.

[`core`](core.md)
: Core package modules (`texsmith`, configuration, contexts, conversion helpers, etc.).

[`bibliography`](bibliography.md)
: Bibliography tooling (BibTeX parsing, DOI resolution, issue reporting).

[`cli`](cli.md)
: Command-line entry points and utilities.

[`handlers`](handlers.md)
: Rendering handlers that transform HTML into LaTeX.

[`latex`](latex.md)
: LaTeX infrastructure (formatter, renderer, templates).

[`markdown`](markdown.md)
: Markdown conversion helpers and custom extensions.

[`plugins`](plugins.md)
: Optional integrations (MkDocs Material-specific handlers).

[`transformers`](transformers.md)
: Asset conversion strategies (SVG, Draw.io, Mermaid, remote images).

Use the navigation sidebar to jump to any section or follow the links above for more detail.
