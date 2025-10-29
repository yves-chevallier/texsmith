# `texsmith render`

`texsmith render` is the primary entry point for turning Markdown or HTML into LaTeX. It can stream fragments to `stdout`, populate a directory with template-aware assets, and—when the `--build` flag is supplied—run `latexmk` to produce ready-to-share PDFs.

```bash
texsmith render [OPTIONS] INPUT... [--bibliography BIBFILE...]
```

## Positional Arguments

| Argument | Description |
| -------- | ----------- |
| `INPUT...` | One or more Markdown (`.md`, `.markdown`) or HTML (`.html`, `.htm`) documents to convert. Positional BibTeX files (`.bib`, `.bibtex`) are detected automatically and merged into the bibliography set. |

When `--build` is enabled, exactly one Markdown/HTML document must be provided.

## Options

| Option | Description |
| ------ | ----------- |
| `--output/-o/--output-dir PATH` | Destination for the rendered output. Pass a file path to write a single `.tex` file, a directory to emit `<stem>.tex` (and template artefacts), or omit the flag to print to `stdout` unless a template dictates otherwise. |
| `--selector TEXT` | CSS selector used to extract article content from HTML inputs. Defaults to `article.md-content__inner`, which matches MkDocs Material pages. |
| `--full-document/--no-full-document` | Render the entire HTML file without applying the selector. Useful for standalone pages that do not follow MkDocs conventions. |
| `--base-level INTEGER` | Offsets detected heading levels before rendering (e.g. `1` turns top-level `#` headings into LaTeX `\section` + 1). |
| `--heading-level/-h INTEGER` | Applies an additional offset during rendering so the document nests deeper inside a template. |
| `--drop-title/--keep-title` | Drop the first document heading. Handy when the template already prints its own title page. |
| `--title-from-heading/--title-from-frontmatter` | Promote the first heading to the template title metadata (compatible with templates that expect front-matter titles). |
| `--numbered/--unnumbered` | Toggle section numbering in the resulting LaTeX. |
| `--parser TEXT` | Selects the BeautifulSoup parser (`html.parser`, `lxml`, `html5lib`, …). Override when the default parser struggles with your HTML. |
| `--no-fallback-converters` | Disable placeholder converters that hide missing optional dependencies (Docker, cairosvg, Pillow, requests). When disabled the command fails immediately if a dependency is unavailable. |
| `--copy-assets/-a/--no-copy-assets/-A` | Control whether referenced assets are copied into the output directory. |
| `--manifest/-m/--no-manifest/-M` | Toggle manifest generation alongside template outputs. |
| `--template/-t PATH_OR_NAME` | Wrap the LaTeX using a template. Accepts a filesystem path or a registered template name, enabling slot-based composition and asset copying. |
| `--debug-html/--no-debug-html` | Persist intermediate HTML snapshots (`*.debug.html`) next to the output to aid debugging. |
| `--language TEXT` | Override the LaTeX language (BCP 47) passed to babel/polyglossia. Defaults to document metadata or template settings. |
| `--legacy-latex-accents/--unicode-latex-accents` | Emit legacy LaTeX accent macros instead of Unicode glyphs. |
| `--slot/-s VALUE` | Map documents or sections to template slots. Syntax: `slot:Selector` for a single document, or `slot:file[:selector]` when converting multiple inputs. Selectors support heading text, `#id`, and the special token `@document` to inject the entire file. |
| `--markdown-extensions/-x VALUE` | Enable additional Markdown extensions. Accepts comma-separated or space-separated lists, or multiple flag occurrences. |
| `--disable-extension/-d VALUE` | Disable default Markdown extensions. Uses the same notation as `--markdown-extensions`. |
| `--bibliography/-b PATH` | Add explicit BibTeX files to the bibliography set. Combine with positional `.bib` inputs as needed. |
| `--build/--no-build` | Invoke `latexmk` after rendering to compile the LaTeX project. Requires `--template` and exactly one Markdown/HTML document. |
| `--classic-output/--rich-output` | When using `--build`, choose between raw `latexmk` output (`--classic-output`) or the structured, live-updating renderer (`--rich-output`, default). |
| `--open-log/--no-open-log` | When `latexmk` fails (with `--build`), open the log file in the system viewer. |

## Usage Examples

### Convert a Markdown page to stdout

```bash
texsmith render docs/getting-started.md
```

The rendered LaTeX is printed to the terminal. Redirect it to save the result:

```bash
texsmith render docs/getting-started.md > build/getting-started.tex
```

### Write the output into a directory

```bash
texsmith render docs/overview.md --output build/
# Produces build/overview.tex
```

### Apply a template and manage slots

```bash
texsmith render docs/intro.md docs/chapter1.md \
  --template article \
  --output-dir build/book \
  --slot frontmatter:docs/intro.md \
  --slot mainmatter:docs/chapter1.md
```

This scenario:

- wraps the LaTeX with the `article` template,
- writes template fragments into `build/book`,
- injects `intro.md` into the `frontmatter` slot and `chapter1.md` into `mainmatter`.

### Compile a PDF with `--build`

```bash
texsmith render docs/manual.md \
  --template article \
  --output-dir build/pdf \
  --build
```

TeXSmith renders the template into `build/pdf`, sets up an isolated TeX cache, and executes `latexmk`. The resulting `manual.pdf` is reported in the build summary.

Need deterministic logs (for CI or scripting)? Switch to classic output:

```bash
texsmith render docs/manual.md \
  --template article \
  --output-dir build/pdf \
  --build \
  --classic-output
```

TeXSmith merges all BibTeX sources and only writes the references that are cited in the document.
