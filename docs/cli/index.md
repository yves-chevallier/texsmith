# TeXSmith Command-Line Interface

TeXSmith ships with a feature-rich CLI that lets you convert Markdown or HTML into LaTeX, compile PDFs, and inspect bibliography files directly from a terminal. The CLI now exposes a single command: `texsmith`. Every flag hangs off that root entry point.

```text
$ texsmith --help

 Usage: texsmith [OPTIONS] INPUT...

 Convert MkDocs documents into LaTeX artefacts and optionally build PDFs.

╭─ Input Handling ─────────────────────────────────────────────────────────────╮
│   inputs      INPUT...  Conversion inputs such as Markdown (.md) or HTML     │
│                         (.html) source documents. Optionally, BibTeX files   │
│                         (.bib) for citation processing.                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --diagrams-backend              BACKEND  Force the backend for diagram       │
│                                          conversion (draw.io, mermaid):      │
│                                          playwright, local, or docker        │
│                                          (auto-default).                     │
│ --embed                                  Embed converted fragments into the  │
│                                          main document instead of using      │
│                                          \input.                             │
│ --classic-output                         Display raw latexmk output without  │
│                                          parsing (use --rich-output for      │
│                                          structured logs).                   │
│ --build                 -b               Invoke latexmk after rendering to   │
│                                          compile the resulting LaTeX         │
│                                          project.                            │
│ --legacy-latex-accents                   Escape accented characters and      │
│                                          ligatures with legacy LaTeX macros  │
│                                          instead of emitting Unicode glyphs  │
│                                          (defaults to Unicode output).       │
│ --list-bibliography                      Print bibliography details from     │
│                                          provided .bib files and exit.       │
│ --template-info                          Display template metadata and exit. │
│ --template-scaffold             DEST     Copy the selected template into     │
│                                          DEST and exit.                      │
│ --fonts-info                             Display a summary of fallback fonts │
│                                          detected during rendering.          │
│ --install-completion                     Install completion for the current  │
│                                          shell.                              │
│ --show-completion                        Show completion for the current     │
│                                          shell, to copy it or customize the  │
│                                          installation.                       │
│ --help                                   Show this message and exit.         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Diagnostics ────────────────────────────────────────────────────────────────╮
│ --list-extensions                   List Markdown extensions enabled by      │
│                                     default and exit.                        │
│ --list-templates                    List available templates (builtin,       │
│                                     entry-point, and local) and exit.        │
│ --verbose          -v      INTEGER  Increase CLI verbosity. Combine multiple │
│                                     times for additional diagnostics.        │
│                                     [default: 0]                             │
│ --debug                             Show full tracebacks when an unexpected  │
│                                     error occurs.                            │
│ --debug-rules                       Display the ordered list of registered   │
│                                     render rules.                            │
│ --debug-html                        Persist intermediate HTML snapshots      │
│                                     (inherits from --debug when omitted).    │
│ --open-log                          Open the latexmk log with the system     │
│                                     viewer when compilation fails.           │
│ --print-context                     Print resolved template context          │
│                                     emitters/consumers and exit.             │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Output ─────────────────────────────────────────────────────────────────────╮
│ --output,--output-dir  -o      PATH  Output file or directory. Defaults to   │
│                                      stdout unless a template is used.       │
│ --makefile-deps        -M            Emit a Makefile-compatible .d           │
│                                      dependency file when building PDFs.     │
│ --html                               Output intermediate HTML instead of     │
│                                      LaTeX/PDF.                              │
│ --engine               -e      TEXT  LaTeX engine backend to use when        │
│                                      building (tectonic, lualatex, xelatex). │
│                                      [default: tectonic]                     │
│ --system               -S            Use the system Tectonic binary instead  │
│                                      of the bundled download.                │
│ --isolate                            Use a per-render TeX cache inside the   │
│                                      output directory instead of the shared  │
│                                      ~/.cache/texsmith cache.                │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Input Handling ─────────────────────────────────────────────────────────────╮
│ --selector             TEXT  CSS selector to extract the MkDocs article      │
│                              content.                                        │
│                              [default: article.md-content__inner]            │
│ --full-document              Disable article extraction and render the       │
│                              entire HTML file.                               │
│ --parser               TEXT  BeautifulSoup parser backend to use (defaults   │
│                              to "html.parser").                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Structure ──────────────────────────────────────────────────────────────────╮
│ --base-level           TEXT  Base heading level relative to the template     │
│                              (e.g. 1 or 'section').                          │
│                              [default: 0]                                    │
│ --strip-heading              Drop the first document heading from the        │
│                              rendered content.                               │
│ --numbered                   Toggle numbered headings. [default: True]       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Template ───────────────────────────────────────────────────────────────────╮
│ --no-promote-title                Disable promotion of the first heading to  │
│                                   document title.                            │
│ --no-title                        Disable title generation even when         │
│                                   metadata provides one.                     │
│ --template          -t      TEXT  Select a LaTeX template to use during      │
│                                   conversion. Accepts a local path, entry    │
│                                   point, or built-in slug such as 'article'  │
│                                   or 'letter'.                               │
│ --attribute         -a      TEXT  Override template attributes as key=value  │
│                                   pairs (e.g. -a emoji=color).               │
│ --slot              -s      TEXT  Inject a document section into a template  │
│                                   slot using 'slot:Section'. Repeat to map   │
│                                   multiple sections.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Rendering ──────────────────────────────────────────────────────────────────╮
│ --no-fallback-converters                  Disable registration of            │
│                                           placeholder converters when Docker │
│                                           is unavailable.                    │
│ --copy-assets             -c    -C        Toggle copying of remote assets to │
│                                           the output directory.              │
│                                           [default: copy-assets]             │
│ --convert-assets                          Convert bitmap assets (PNG/JPEG)   │
│                                           to PDF even when LaTeX supports    │
│                                           the original format.               │
│ --hash-assets                             Hash stored asset filenames        │
│                                           instead of preserving their        │
│                                           original names.                    │
│ --manifest                -m              Generate a manifest.json file      │
│                                           alongside the LaTeX output.        │
│ --language                -l        TEXT  Language code passed to babel      │
│                                           (defaults to metadata or english). │
│ --markdown-extensions     -x        TEXT  Additional Markdown extensions to  │
│                                           enable (comma or space separated   │
│                                           values are accepted).              │
│ --disable-extension       -d        TEXT  Markdown extensions to disable.    │
│                                           Provide a comma separated list or  │
│                                           repeat the option multiple times.  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Options

`--diagrams-backend`
: When TeXSmith discovers diagrams in your Markdown (e.g., Mermaid or Draw.io), it needs to convert them into image files that LaTeX can include. This option forces a specific backend for that conversion, overriding the automatic selection logic. Supported backends include `playwright` (headless browser), `local` (locally installed CLI tools), and `docker` (containerized tools).

`--embed`
: By default, TeXSmith renders converted documents as separate LaTeX files and links them into the main document using `\input{}`. This option inlines the converted LaTeX documents directly into the main document body instead. This can be useful for simpler projects where a single `.tex` file is preferred.

`--classic-output`
: When building PDFs, TeXSmith normally parses and structures the output from `latexmk` to provide cleaner logs and richer diagnostics. This option disables that behavior and streams the raw `latexmk` output directly to your terminal. You can disable structured logs temporarily with this option.

`--build`
: After rendering the LaTeX document from your Markdown sources, invoke the default engine `tectonic` by default or the engine specified via `--engine` to compile the LaTeX into a PDF.

`--legacy-latex-accents`
: By default, TeXSmith emits Unicode characters for accented letters and ligatures (e.g., é, ñ, æ) when generating LaTeX output. This option switches to using legacy LaTeX macros (e.g., `\'{e}`, `\~{n}`, `\ae{}`) instead, which may be necessary for compatibility with older LaTeX engines or templates.

`--list-bibliography`
: Display a summary of all bibliography entries found in the provided `.bib` files, front matter or doi links. This is useful for validating bibliography sources without performing a full document render.

`--template-info`
: Show detailed metadata about the selected template, including its attributes, slots, and assets. This is helpful for understanding how to customize or extend a template.

`--fonts-info`
: After rendering, display a summary of the fonts used in the generated LaTeX document, including any fallback fonts that were selected based on the document's language and content.

`--install-completion`, `--show-completion`
: Install or display shell completion scripts for the TeXSmith CLI. This enhances your terminal experience by providing auto-completion for commands and options.

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
