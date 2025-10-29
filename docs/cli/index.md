# TeXSmith Command-Line Interface

TeXSmith ships with a feature-rich CLI that lets you convert Markdown or HTML into LaTeX, compile PDFs, and inspect bibliography files directly from a terminal. All commands follow the same pattern:

```bash
texsmith [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS] ...
```

This page explains the global behaviour of the CLI, highlights the available subcommands, and directs you toward detailed documentation for each command.

## Global Options

These options must appear before the subcommand name and affect every command.

| Option | Description |
| ------ | ----------- |
| `--list-extensions` | Print the Markdown extensions enabled by default, then exit. |
| `-v / --verbose` | Increase logging verbosity. Stack with `-vv` or more to surface richer diagnostics. |
| `--debug / --no-debug` | Show full Python tracebacks when an unexpected exception occurs. |
| `--help` | Display contextual help for the CLI or the selected subcommand. |

Example:

```bash
texsmith --debug -vv render docs/chapter.md
```

## Available Commands

- [`render`](render.md) – Convert Markdown/HTML documents to LaTeX fragments or template-aware outputs, optionally building PDFs.
- [`bibliography`](bibliography.md) – Inspect BibTeX files and surface parsing issues.

Each command has its own options and usage examples on the linked pages.

## Quick Start

```bash
# Generate LaTeX fragments from Markdown
texsmith render intro.md --output build/

# Render with a template and latexmk
texsmith render intro.md --template article --output-dir build/pdf --build

# Inspect bibliography sources
texsmith bibliography list references.bib
```

Refer to `texsmith COMMAND --help` whenever you need the most up-to-date option list, defaults, and environment-specific notes.

## Diagnostics

Every CLI command routes warnings, errors, and structured events through the new `DiagnosticEmitter` interface. The Typer apps instantiate a `CliEmitter`, so verbosity flags (`-v`) control how much detail reaches your terminal. Library consumers can provide their own emitter to capture the same diagnostics programmatically when embedding TeXSmith.
