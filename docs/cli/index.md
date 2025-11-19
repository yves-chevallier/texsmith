# TeXSmith Command-Line Interface

TeXSmith ships with a feature-rich CLI that lets you convert Markdown or HTML into LaTeX, compile PDFs, and inspect bibliography files directly from a terminal.

```bash
$ texsmith --help
 Usage: texsmith [OPTIONS] COMMAND [ARGS]...

 Convert MkDocs HTML fragments into LaTeX.

╭─ Options ────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.          │
│ --show-completion             Show completion for the current shell, to copy it  │
│                               or customize the installation.                     │
│ --help                        Show this message and exit.                        │
╰──────────────────────────────────────────────────────────────────────────────────╯
╭─ Diagnostics ────────────────────────────────────────────────────────────────────╮
│ --list-extensions                             List Markdown extensions enabled   │
│                                               by default and exit.               │
│ --verbose          -v                INTEGER  Increase CLI verbosity. Combine    │
│                                               multiple times for additional      │
│                                               diagnostics.                       │
│                                               [default: 0]                       │
│ --debug                --no-debug             Show full tracebacks when an       │
│                                               unexpected error occurs.           │
│                                               [default: no-debug]                │
╰──────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────╮
│ render         Convert MkDocs documents into LaTeX artefacts and optionally      │
│                build PDFs.                                                       │
│ bibliography   Inspect and interact with BibTeX bibliography files.              │
│ latex          Inspect LaTeX templates and runtime data.                         │
│ template       Inspect LaTeX templates available to TeXSmith.                    │
╰──────────────────────────────────────────────────────────────────────────────────╯

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

## Available Commands and Flags

[`render`](render.md)
: Convert Markdown/HTML documents to LaTeX fragments or template-aware outputs, optionally building PDFs. This is also the default action when you run `texsmith` without an explicit subcommand.

[`--list-bibliography`](bibliography.md)
: Load one or more BibTeX files and surface parsing issues without rendering.

[`--template-info`, `--template-scaffold`](template.md)
: Inspect manifest metadata, attributes, assets, and slots for any installed or local template, or copy a template tree to a writable directory for customization.

Each option has its own usage examples on the linked pages.

## Quick Start

```bash
# Generate LaTeX fragments from Markdown
texsmith render intro.md --output build/

# Render with a template and latexmk
texsmith render intro.md --template article --output-dir build/pdf --build

# Inspect bibliography sources
texsmith references.bib --list-bibliography
```

Refer to `texsmith COMMAND --help` whenever you need the most up-to-date option list, defaults, and environment-specific notes.

## Diagnostics

Every CLI command routes warnings, errors, and structured events through the new `DiagnosticEmitter` interface. The Typer apps instantiate a `CliEmitter`, so verbosity flags (`-v`) control how much detail reaches your terminal. Library consumers can provide their own emitter to capture the same diagnostics programmatically when embedding TeXSmith.
