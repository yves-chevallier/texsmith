# TeXSmith Command-Line Interface

TeXSmith ships with a feature-rich CLI that lets you convert Markdown or HTML into LaTeX, compile PDFs, and inspect bibliography files directly from a terminal. The CLI now exposes a single command: `texsmith`. Every flag hangs off that root entry point.

```text
$ texsmith --help
--8<--- "docs/assets/cli-help"
```

## Options

### General Options

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

`--install-completion`, `--show-completion`
: Install or display shell completion scripts for the TeXSmith CLI. This enhances your terminal experience by providing auto-completion for commands and options.

`--help`
: Show contextual help for the TeXSmith CLI, including available commands and options.

### Diagnostics Options

`--list-extensions`
: Print a list of all Markdown extensions that are enabled by default during conversion. This is useful for understanding how your Markdown will be processed.

`--list-templates`
: Show detailed metadata about the selected template, including its attributes, slots, and assets. This is helpful for understanding how to customize or extend a template.

`--list-bibliography`
: Display a summary of all bibliography entries found in the provided `.bib` files, front matter or doi links. This is useful for validating bibliography sources without performing a full document render.

`--debug`
: Enable detailed debugging output for the CLI. This includes full Python tracebacks when unexpected exceptions occur, which can help diagnose issues during conversion or rendering.

`--debug-rules`
: Print the ordered list of registered render rules that TeXSmith applies during conversion. This is useful for understanding the transformation pipeline.

`--debug-html`
: Save intermediate HTML snapshots generated during the conversion process. This can help diagnose issues related to HTML parsing or content extraction.

`--open-log`
: If LaTeX compilation fails during the build step, automatically open the `latexmk` log file using the system's default viewer. This makes it easier to inspect compilation errors.

`--template-info`
: Show manifest metadata for the template selected via `--template`, including its attributes, assets, and slots.

`--fonts-info`
: After rendering, display a summary of the fonts used in the generated LaTeX document, including any fallback fonts that were selected based on the document's language and content.

`--print-context`
: Print the resolved template context, including all emitters and consumers, then exit. This is useful for debugging template rendering issues.

### Output Options

`--output`, `--output-dir`
: Specify the output file or directory for the rendered LaTeX or compiled PDF. If no output path is provided, TeXSmith defaults to writing to `stdout` unless a template is used.

`--makefile-deps`
: When building PDFs, generate a Makefile-compatible `.d` dependency file alongside the output. This can be useful for integrating TeXSmith into larger build systems.

`--html`
: Instead of generating LaTeX or PDF output, emit the intermediate HTML produced during the conversion process. This is useful for inspecting how your Markdown is transformed into HTML.

`--engine`
: Specify the LaTeX engine to use when compiling the rendered document into a PDF. Supported engines include `tectonic`, `lualatex`, and `xelatex`. The default is `tectonic`.

`--system`
: Use the system-installed Tectonic binary instead of the bundled version provided by TeXSmith. This can be useful if you have a specific version of Tectonic installed or want to leverage system-wide configurations.

`--isolate`
: By default, TeXSmith uses a shared cache located at `~/.cache/texsmith` to store compiled LaTeX artifacts. This option creates a per-render cache inside the output directory, isolating the build environment for each project.

### Input Handling Options

`--selector`
: When converting HTML documents (e.g., from MkDocs), this option specifies a CSS selector to extract the main article content. The default selector is `article.md-content__inner`, which targets the primary content area.

`--full-document`
: Disable article extraction and render the entire HTML file as-is. This is useful when you want to convert a complete HTML document rather than just the main content.

`--parser`
: Specify the BeautifulSoup parser backend to use when parsing HTML input. The default is `html.parser`, but you can choose other parsers like `lxml` if they are installed.

### Structure Options

`--base-level`
: Set the base heading level for the document relative to the template. For example, if your template starts at level 1 (e.g., `\section{}`), you can adjust the base level accordingly. The default is `0`. We use the convention where `-1` is `\part{}`, `0` is `\chapter{}`, `1` is `\section{}`, and so on.

`--strip-heading`
: Remove the first heading from the rendered content. This is useful when the first heading is redundant with the document title or when you want to avoid duplicate titles or keep the first heading as information only.

### Template Options

`--no-promote-title`
: By default, TeXSmith promotes the first heading in the document to be the title of the LaTeX document. This option disables that behavior, keeping the first heading as part of the main content. If not title is found in metadata or front matter, no title will be generated.

`--no-title`
: Disable title generation entirely, even if metadata or front matter provides a title. This is useful when you want to suppress the title page in the rendered document.

`--template`, `-t`
: Select a LaTeX template to use during conversion. You can provide a local path, an entry point, or a built-in slug such as `article`, `book` or `letter`.

`--attribute`, `-a`
: Override template attributes by providing key=value pairs. This allows you to customize template behavior without modifying the template files directly. You can repeat this option multiple times to set multiple attributes.

`--slot`, `-s`
: Inject specific document sections into designated template slots using the syntax `slot:Section`. You can repeat this option multiple times to map multiple sections to different slots in the template.

### Rendering Options

`--no-fallback-converters`
: Disable the registration of placeholder converters that TeXSmith uses when Docker is unavailable. This ensures that only fully supported conversion paths are used.

`--no-copy-assets`, `-C`
: Control whether remote assets (e.g., images, diagrams) are copied to the output directory during rendering. By default, assets are copied to ensure they are available for LaTeX compilation. You can disable this behavior.

`--convert-assets`
: Convert bitmap assets (e.g., PNG, JPEG) to PDF format even when LaTeX supports the original format. This can improve compatibility and rendering quality in some cases.

`--hash-assets`
: Hash the filenames of stored assets instead of preserving their original names. This helps avoid filename collisions when multiple assets with the same name are used in different documents.

`--manifest`, `-m`
: Generate a `manifest.json` file alongside the LaTeX output, containing metadata about the rendered document, including input sources, template details, and rendering options.

`--language`, `-l`
: Specify the language code to pass to the LaTeX `babel` package. This affects hyphenation and language-specific typographic rules. If not provided, TeXSmith uses the language specified in the document metadata or defaults to English.

`--enable-extension`, `-x`
: Enable additional Markdown extensions during conversion. You can repeat this option multiple times or provide a comma-separated list of extensions to activate.

`--disable-extension`, `-X`
: Disable specific Markdown extensions during conversion. You can repeat this option multiple times or provide a comma-separated list of extensions to deactivate.

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
