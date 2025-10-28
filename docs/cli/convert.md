# `texsmith convert`

`texsmith convert` transforms Markdown or HTML sources into LaTeX. It can emit the result to standard output, write `.tex` files, or wrap the content in a LaTeX template complete with slots and assets.

```bash
texsmith convert [OPTIONS] INPUT... [--bibliography BIBFILE...]
```

## Positional Arguments

| Argument | Description |
| -------- | ----------- |
| `INPUT...` | One or more Markdown (`.md`, `.markdown`) or HTML (`.html`, `.htm`) documents to convert. BibTeX files (`.bib`, `.bibtex`) provided positionally are detected automatically and merged into the bibliography set. |

## Options

| Option | Description |
| ------ | ----------- |
| `--output/-o PATH` | Controls where the LaTeX is written. If `PATH` is a file (e.g. `article.tex`) a single file is produced. If `PATH` is a directory, TeXSmith writes `<stem>.tex` inside that directory for each input. Without this flag the result is printed to `stdout`, unless a template dictates otherwise. |
| `--selector TEXT` | CSS selector used to extract the main article content from HTML inputs. Defaults to `article.md-content__inner`, which suits MkDocs Material. Adjust this when your HTML structure differs. |
| `--full-document / --no-full-document` | Forces conversion of the entire HTML file, bypassing the selector. Useful for standalone pages that do not follow MkDocs conventions. |
| `--base-level INTEGER` | Shifts the detected heading levels before rendering (e.g. `1` turns top-level `#` headings into LaTeX `\section` + 1). Helpful when your template expects a specific base level. |
| `--heading-level/-h INTEGER` | Adds an extra offset while rendering headings. Use it to nest the document deeper inside a template without editing the source Markdown. |
| `--drop-title / --keep-title` | Drops the first heading encountered. Typically used when the template already prints its own title page. |
| `--numbered / --unnumbered` | Toggles section numbering in the rendered LaTeX. Disable numbering for appendices or frontmatter. |
| `--parser TEXT` | Selects the BeautifulSoup parser (`html.parser`, `lxml`, `html5lib`, …). Pick one when the default parser fails to handle your HTML. |
| `--no-fallback-converters` | Prevents TeXSmith from installing placeholder converters when optional dependencies (Docker, cairosvg, Pillow, requests) are missing. Without fallbacks the command fails immediately. |
| `--copy-assets / --no-copy-assets` | Controls whether assets (images, generated diagrams, remote resources) are copied into the output directory. Disable copying if assets are handled externally. |
| `--manifest / --no-manifest` | Toggles manifest generation. Reserved for advanced workflows; most users can ignore it. |
| `--template/-t PATH_OR_NAME` | Wraps the LaTeX using a template. Accepts a filesystem path or a registered template name. Templates enable slot-based composition, asset copying, and optional manifest output. |
| `--debug-html / --no-debug-html` | Persists the intermediate HTML snapshot (`*.debug.html`) alongside the output. Enable it when diagnosing Markdown conversion issues. |
| `--language TEXT` | Overrides the LaTeX language (BCP 47) passed to babel/polyglossia. Falls back to metadata or template defaults when omitted. |
| `--slot/-s VALUE` | Maps documents or sections to template slots. Syntax: `slot:Selector` for a single document, or `slot:file[:section]` when converting multiple inputs. Selectors accept headings (by text or `#id`) as well as special tokens such as `@document` to inject the entire file. |
| `--markdown-extensions/-x VALUE` | Enables additional Markdown extensions. Accepts comma-separated or space-separated lists, or multiple flag occurrences. |
| `--disable-extension/-d VALUE` | Disables default Markdown extensions. Uses the same notation as `--markdown-extensions`. |
| `--bibliography/-b PATH` | Adds explicit BibTeX files to the bibliography set. Combine with positional `.bib` inputs as needed. |

## Usage Examples

### Convert a Markdown page to stdout

```bash
texsmith convert docs/getting-started.md
```

The rendered LaTeX is printed to the terminal. Redirect it to save the result:

```bash
texsmith convert docs/getting-started.md > build/getting-started.tex
```

### Write the output into a directory

```bash
texsmith convert docs/overview.md --output build/
# Produces build/overview.tex
```

### Apply a template and manage slots

```bash
texsmith convert docs/intro.md docs/chapter1.md \
  --template article \
  --output build/book \
  --slot frontmatter:docs/intro.md \
  --slot mainmatter:docs/chapter1.md
```

This scenario:

- wraps the LaTeX with the `article` template,
- writes template fragments into `build/book`,
- injects `intro.md` into the `frontmatter` slot and `chapter1.md` into `mainmatter`.

### Include bibliography files

```bash
texsmith convert docs/article.md references/papers.bib --bibliography refs/extra.bib
```

TeXSmith merges all BibTeX sources and only writes the references that are actually cited in the document.
