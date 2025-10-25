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
| `--list-extensions` | Prints the Markdown extensions enabled by default, then exits immediately. |
| `-v / --verbose` | Increases logging verbosity. Repeat the flag (e.g. `-vv`) to surface progressively more diagnostic information. |
| `--debug / --no-debug` | Enables full Python tracebacks so unexpected exceptions are not swallowed. Useful while customising converters or templates. |
| `--help` | Displays contextual help for the CLI or a specific command. |

Example:

```bash
texsmith --debug -vv convert docs/chapter.md
```

## Available Commands

- [`convert`](convert.md) – Convert Markdown/HTML documents to LaTeX fragments or template-aware outputs.
- [`build`](build.md) – Convert documents and run `latexmk` to produce a finished PDF.
- [`bibliography`](bibliography.md) – Inspect BibTeX files and surface parsing issues.

Each command has its own options and usage examples on the linked pages.

## Quick Start

```bash
# Generate a LaTeX file from Markdown
texsmith convert docs/tutorial.md --output build/

# Compile the same document all the way to PDF
texsmith build docs/tutorial.md \
  --template texsmith/templates/article \
  --output-dir build

# Audit bibliography files before conversion
texsmith bibliography list references/*.bib
```

Refer to `texsmith COMMAND --help` whenever you need the most up-to-date option list, defaults, and environment-specific notes.
