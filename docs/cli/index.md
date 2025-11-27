# TeXSmith Command-Line Interface

TeXSmith ships with a feature-rich CLI that lets you convert Markdown or HTML into LaTeX, compile PDFs, and inspect bibliography files directly from a terminal. The CLI now exposes a single command: `texsmith`. Every flag hangs off that root entry point.

```bash
$ texsmith --help

 Usage: texsmith [OPTIONS] INPUT...

 Convert MkDocs documents into LaTeX artefacts and optionally build PDFs.

╭─ Input Handling ─────────────────────────────────────────────────────────────╮
│   inputs      INPUT...  Conversion inputs. Provide a Markdown/HTML source    │
│                         document and optionally one or more BibTeX files.    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --classic-output   --rich-output        Display raw engine output without    │
│                                          parsing (use --rich-output for      │
│                                          structured logs).                   │
│ --build            --no-build           Invoke the selected engine after     │
│                                          rendering to compile the resulting  │
│                                          LaTeX project.                      │
│ --legacy-latex-accents/--unicode-latex-accents …                             │
│ --list-bibliography                      Print bibliography details from     │
│                                          provided .bib files and exit.       │
│ --template-info                          Display template metadata and exit. │
│ --template-scaffold DEST                 Copy the selected template into     │
│                                          DEST and exit.                      │
│ --list-extensions                        List Markdown extensions enabled    │
│                                          by default and exit.                │
│ --list-templates                         List available templates and exit.  │
│ -v, --verbose                            Increase CLI verbosity (stackable). │
│ --debug/--no-debug                       Show full tracebacks on errors.     │
│ --help                                   Show this message and exit.         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

This page explains the global behaviour of the CLI, highlights the most important flags, and points toward detailed documentation for specific workflows.
Use `--engine tectonic|lualatex|xelatex` to pick the PDF compiler; Tectonic is the default.

## Global Options

These options can be combined with any conversion run:

| Option | Description |
| ------ | ----------- |
| `--list-extensions` | Print the Markdown extensions enabled by default, then exit. |
| `--list-templates` | Enumerate built-in, entry-point, and local templates. |
| `--list-bibliography` | Inspect one or more `.bib` files without rendering. |
| `--template-info` | Show manifest metadata for the template selected via `--template`. |
| `--template-scaffold DEST` | Copy the selected template into `DEST` for easy customization. |
| `-v / --verbose` | Increase logging verbosity. Stack with `-vv` or more to surface richer diagnostics. |
| `--debug / --no-debug` | Show full Python tracebacks when an unexpected exception occurs. |
| `--help` | Display contextual help for the CLI. |

Example:

```bash
texsmith --debug -vv docs/chapter.md --template article --build
```

## Rendering Options

See [`render`](render.md) for the complete list of conversion flags (structure adjustments, Markdown extensions, template attributes, slots, and engine controls). Every example there works whether or not you type the legacy `render` verb, but the canonical form is now `texsmith …`.

[`--list-bibliography`](bibliography.md)
: Load one or more BibTeX files and surface parsing issues without rendering. Combine it with your document inputs to validate bibliography assets alongside the main build.

[`--template-info`, `--template-scaffold`](template.md)
: Inspect manifest metadata, attributes, assets, and slots for any installed or local template, or copy a template tree to a writable directory for customization.

Each option has its own usage examples on the linked pages.

## Quick Start

```bash
# Generate LaTeX fragments from Markdown
texsmith intro.md --output build/

# Render with a template and compile to PDF (default = Tectonic)
texsmith intro.md --template article --output-dir build/pdf --build

# Inspect bibliography sources
texsmith references.bib --list-bibliography
```

Refer to `texsmith COMMAND --help` whenever you need the most up-to-date option list, defaults, and environment-specific notes.

## Diagnostics

Every CLI invocation routes warnings, errors, and structured events through the `DiagnosticEmitter` interface. The Typer app instantiates a `CliEmitter`, so verbosity flags (`-v`) control how much detail reaches your terminal. Library consumers can provide their own emitter to capture the same diagnostics programmatically when embedding TeXSmith.
