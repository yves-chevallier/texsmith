# TeXSmith Command-Line Interface

TeXSmith ships with a feature-rich CLI that lets you convert Markdown or HTML into LaTeX, compile PDFs, and inspect bibliography files directly from a terminal. Conversion is the root entry point itself: `texsmith doc.md --build`, with every flag hanging off `texsmith`.

```text
$ texsmith --help
--8<--- "docs/assets/cli-help"
```

Everything that is not a conversion sits in a command group of its own, reached by its name.

`texsmith site assets [CONFIG]`
: Write the files a documentation site cannot produce while it renders — the stylesheet, one preview per `.snippet` fence and one SVG per `.drawio` image — under the site's `docs_dir`, where the generator copies them as sources. `CONFIG` defaults to the first of `mkdocs.yml`, `mkdocs.yaml` or `zensical.toml` in the current directory. Run it before `zensical build`; see [Zensical](../guide/mkdocs.md#zensical).

`texsmith site search [CONFIG]`
: Add the index entries of every page (`#[term]`) to the `tags` field of the lunr index under `site_dir` — MkDocs' `search/search_index.json`, which Material searches and boosts. The plugin does the same from `on_post_build`, so this is for an index written without it. A Zensical site is left alone: its search reads the terms as a page's `tags`, written while the page renders.

`texsmith site build [CONFIG]`
: Build the PDF books the site declares under its `texsmith:` options, the same way `mkdocs build` builds them from `on_post_build`: the navigation is resolved, every page is pre-passed so the book carries the site's numbers, and each book's bundle is written under `build_dir` and compiled. `--build-dir DIR`, `--book TITLE`, `--no-pdf`, and `--strict` / `--diagnostics-json` as on the root command. See [The book is a command](../guide/mkdocs.md#the-book-is-a-command).

## Options

### General Options

`--version`
: Print the installed TeXSmith version and exit. The same value is available in Python as `texsmith.get_version()`.

`--diagrams-backend`
: When TeXSmith discovers diagrams in your Markdown (e.g., Mermaid or Draw.io), it needs to convert them into image files that LaTeX can include. This option forces a specific backend for that conversion, overriding the automatic selection logic. Supported backends include `playwright` (headless browser), `local` (locally installed CLI tools), and `docker` (containerized tools).

`--embed`
: By default, TeXSmith renders converted documents as separate LaTeX files and links them into the main document using `\input{}`. This option inlines the converted LaTeX documents directly into the main document body instead. This can be useful for simpler projects where a single `.tex` file is preferred.

`--classic-output`
: When building PDFs, TeXSmith normally parses and structures the output from `latexmk` to provide cleaner logs and richer diagnostics. This option disables that behavior and streams the raw `latexmk` output directly to your terminal. You can disable structured logs temporarily with this option.

`--build`
: After rendering the LaTeX document from your Markdown sources, invoke the default engine (`tectonic`) or the engine specified via `--engine` to compile the LaTeX into a PDF.

`--legacy-latex-accents`
: By default, TeXSmith emits Unicode characters for accented letters and ligatures (e.g., é, ñ, æ) when generating LaTeX output. This option switches to using legacy LaTeX macros (e.g., `\'{e}`, `\~{n}`, `\ae{}`) instead, which may be necessary for compatibility with older LaTeX engines or templates.

`--template-scaffold DEST`
: Copy the template selected with `--template` into `DEST` and exit, so you can edit a copy of a built-in instead of starting from a blank directory. See [Templates](templates.md#scaffolding-custom-templates).

`--install-completion`, `--show-completion`
: Install or display shell completion scripts for the TeXSmith CLI. This enhances your terminal experience by providing auto-completion for commands and options.

`--help`
: Show contextual help for the TeXSmith CLI, including available commands and options.

### Diagnostics Options

`--list-templates`
: List all discoverable templates, along with their origins and paths.

`--list-bibliography`
: Display a summary of all bibliography entries found in the provided `.bib` files, front matter, or DOI links. This is useful for validating bibliography sources without performing a full document render.

`-v`, `--verbose`
: Increase CLI verbosity; repeat it (`-vv`) for more. At `-v` a diagnostic also prints its suggested fix and related locations, indented under its line.

`--debug`
: Enable detailed debugging output for the CLI. This includes full Python tracebacks when unexpected exceptions occur, which can help diagnose issues during conversion or rendering. It also turns `--debug-ir` on unless that flag is given explicitly.

`--debug-ir`
: Save the parsed IR of each document as `<stem>.ir.json` next to the output. This is what the passes see and what `tmark.write` turns into a body, so it is the first place to look when a construct does not render as expected.

`-q`, `--quiet`
: Hide `hint` and `info` diagnostics. Warnings and errors are always shown.

`--strict`
: Exit with status 1 when any warning or error was recorded, after the LaTeX is written and before the engine runs. `press.features.strict: true` in the front matter has the same effect. See [Diagnostics](../guide/diagnostics.md).

`--deprecated LEVEL`
: The transition knob of the parser. TMark reports the legacy spellings it still accepts — root `counters:` instead of `press.declare.counters`, `#{prefix:key}` instead of `#(prefix:key)`, `[^key]` citations — as `deprecated` and `deprecated-frontmatter-key` warnings, which would fail `--strict` on a document that has not been rewritten yet (`tmark lint --fix` does the rewrite). `warning` (the default) keeps them as they are; `info` lowers them to `info` records, so they still print but do not fail `--strict` (and `-q` hides them); `off` drops them entirely. Applied before the strict check and the `--diagnostics-json` dump. `press.diagnostics.deprecated: info` (or `off`) in the front matter sets the same level; the CLI option wins. Every other warning is untouched.

`--diagnostics-json PATH`
: Write every recorded diagnostic to `PATH` as a JSON list, sorted by file and position, for editors and CI.

`--open-log`
: If LaTeX compilation fails during the build step, automatically open the `latexmk` log file using the system's default viewer. This makes it easier to inspect compilation errors.

`--dump-snippets DIR`
: Copy the sources of every `.snippet` fence render (the generated `.tex` and its auxiliary files) into `DIR`, so a preview that comes out wrong can be compiled by hand.

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

`--format`
: Choose the output backend: `latex` (default) or `typst`. Both backends consume the same intermediate representation; `typst` emits a `.typ` source (add `--build` to compile it to PDF). The Typst path does not support `--template-info` or `--template-scaffold`. See [Output backends](../guide/plumbing/backends.md) for installation and scope.

`--engine`
: Specify the LaTeX engine to use when compiling the rendered document into a PDF (LaTeX backend only). Supported engines include `tectonic`, `lualatex`, and `xelatex`. The default is `tectonic`.

`--system`
: Use the system-installed Tectonic binary instead of the bundled version provided by TeXSmith. This can be useful if you have a specific version of Tectonic installed or want to leverage system-wide configurations.

`--isolate`
: By default, TeXSmith uses a shared cache located at `~/.cache/texsmith` to store compiled LaTeX artifacts. This option creates a per-render cache inside the output directory, isolating the build environment for each project.

### Input Handling Options

`--include-path PATH`
: A directory an include falls back to when its path does not resolve against the file that writes it. Repeat the option to name several; they are searched in the order given. The including file's own directory always comes first, so `{include}(file)` keeps the meaning the [syntax reference](../syntax/index.md) gives it — the search path only rescues a path written against somewhere else, which is what the deprecated `--8<-- "file"` spelling does: MkDocs resolves those against the `base_path` of `pymdownx.snippets`, usually the directory of `mkdocs.yml`. A document can carry the same list itself as `press.include_paths` in its front matter, written relative to the document; `--include-path` is searched before it, and the MkDocs plugin's own `base_path` after it.

### Structure Options

`--base-level`
: Set the base heading level for the document relative to the template. For example, if your template starts at level 1 (e.g., `\section{}`), you can adjust the base level accordingly. The default is `0`. We use the convention where `-1` is `\part{}`, `0` is `\chapter{}`, `1` is `\section{}`, and so on.

`--strip-heading`
: Remove the first heading from the rendered content. This is useful when the first heading is redundant with the document title or when you want to avoid duplicate titles or keep the first heading as information only.

### Template Options

`--no-promote-title`
: By default, TeXSmith promotes the first heading in the document to be the title of the LaTeX document. This option disables that behavior, keeping the first heading as part of the main content. If no title is found in metadata or front matter, no title will be generated.

`--no-title`
: Disable title generation entirely, even if metadata or front matter provides a title. This is useful when you want to suppress the title page in the rendered document.

`--template`, `-t`
: Select a LaTeX template to use during conversion. You can provide a local path, an entry point, or a built-in slug such as `article`, `book`, or `letter`.

`--enable-fragment`, `-f` / `--disable-fragment`, `-F`
: Add or remove one [fragment](../guide/templates/fragments.md) for this render, on top of what the template defaults and `press.fragments` decided. Repeat either to name several. A contract fragment the writer requires cannot be dropped this way — a body that emits `\tscallout` still activates `ts-callouts`.

`--attribute`, `-a`
: Override template attributes by providing key=value pairs. This allows you to customize template behavior without modifying the template files directly. You can repeat this option multiple times to set multiple attributes.

`--slot`, `-s`
: Inject specific document sections into designated template slots using the syntax `slot:Section`. You can repeat this option multiple times to map multiple sections to different slots in the template.

### Rendering Options

`--no-copy-assets`, `-C`
: Control whether remote assets (e.g., images, diagrams) are copied to the output directory during rendering. By default, assets are copied to ensure they are available for LaTeX compilation. You can disable this behavior.

`--convert-assets`
: Convert bitmap assets (e.g., PNG, JPEG) to PDF format even when LaTeX supports the original format. This can improve compatibility and rendering quality in some cases.

`--hash-assets`
: Hash the filenames of stored assets instead of preserving their original names. This helps avoid filename collisions when multiple assets with the same name are used in different documents.

`--http-user-agent`
: Override the User-Agent header used when fetching remote assets (images, emoji). You can also set `TEXSMITH_HTTP_USER_AGENT` in the environment.

`--manifest`, `-m`
: Generate a `manifest.json` file alongside the LaTeX output, containing metadata about the rendered document, including input sources, template details, and rendering options.

`--language`, `-l`
: Specify the language code to pass to the LaTeX `babel` package. This affects hyphenation and language-specific typographic rules. If not provided, TeXSmith uses the language specified in the document metadata or defaults to English. On the `tmark` reader the same resolved language, as a BCP 47 primary subtag (`french` → `fr`, `ngerman` → `de`, `english` → `en`), is also handed to TMark's resolver and writers (`lang`), which pick the label words of the predeclared series from it.

`--numbering MODE`
: Who allocates the numbers of the predeclared series — figures, tables, listings, equations, sections and the theorem kinds. `backend` (the default) leaves them to LaTeX and Typst, each numbering its own floats as it always did, so a `Figure 3.2` in the PDF may be a `Figure 12` in the Typst output. `tmark` makes TMark allocate them once, at resolve time, in document order and continuously across the documents of a batch (`ResolveOptions.numbering: all`), and both writers print those numbers in the cross-references: `\hyperref[tbl:one]{Table~1}` in the `.tex`, `#link(<tbl:one>)[Table 1]` in the `.typ`, identical on both backends. Only labelled items (a caption with `{#fig:x}`) take a number; the float's own caption is still numbered by the backend, so use `tmark` numbering where the two must agree (the web profile, a site built page by page) and keep `backend` for a print-only document with chapter-scoped numbers. User counters declared under `press.declare.counters` are always TMark-numbered, whatever the mode.

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
