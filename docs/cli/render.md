# TeXSmith CLI

`texsmith` is the primary entry point for turning Markdown or HTML into LaTeX. It
can stream fragments to `stdout`, populate a directory with template-aware assets, and—when
the `--build` flag is supplied—run `latexmk` to produce ready-to-share PDFs. The legacy
`render` verb still works (for muscle memory), but the canonical form is simply `texsmith`.

!!! tip
    Handy inspection flags live at the top level:

    - `texsmith --list-extensions` dumps the default Markdown extension stack.
    - `texsmith --list-templates` enumerates built-in, entry-point, and local templates.
    - `texsmith bibliography.bib --list-bibliography` formats BibTeX entries without rendering.
    - `texsmith --template ./templates/report --template-info` prints manifest metadata.
    - `texsmith --template article --template-scaffold scaffold-dir/` copies a template for tweaking.
    - `texsmith --debug-rules` dumps the ordered list of renderer rules for debugging extensions.

```bash
$ uv run texsmith --help

 Usage: texsmith [OPTIONS] INPUT...

 Convert MkDocs documents into LaTeX artefacts and optionally build PDFs.

╭─ Input Handling ───────────────────────────────────────────────────────────────────╮
│   inputs      INPUT...  Conversion inputs. Provide a Markdown/HTML source document │
│                         and optionally one or more BibTeX files.                   │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────╮
│ --classic-output          --rich-output                Display raw latexmk output  │
│                                                        without parsing (use        │
│                                                        --rich-output for           │
│                                                        structured logs).           │
│                                                        [default: rich-output]      │
│ --build                   --no-build                   Invoke latexmk after        │
│                                                        rendering to compile the    │
│                                                        resulting LaTeX project.    │
│                                                        [default: no-build]         │
│ --legacy-latex-accents    --unicode-latex-accents      Escape accented characters  │
│                                                        and ligatures with legacy   │
│                                                        LaTeX macros instead of     │
│                                                        emitting Unicode glyphs     │
│                                                        (defaults to Unicode        │
│                                                        output).                    │
│                                                        [default:                   │
│                                                        unicode-latex-accents]      │
│ --help                                                 Show this message and exit. │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Output ───────────────────────────────────────────────────────────────────────────╮
│ --output,--output-dir  -o      PATH  Output file or directory. Defaults to stdout  │
│                                      unless a template is used.                    │
│ --isolate                            Use a per-render TeX cache inside the output  │
│                                      directory instead of the shared               │
│                                      ~/.cache/texsmith cache.                      │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Input Handling ───────────────────────────────────────────────────────────────────╮
│ --selector             TEXT  CSS selector to extract the MkDocs article content.   │
│                              [default: article.md-content__inner]                  │
│ --full-document              Disable article extraction and render the entire HTML │
│                              file.                                                 │
│ --parser               TEXT  BeautifulSoup parser backend to use (defaults to      │
│                              "html.parser").                                       │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Structure ────────────────────────────────────────────────────────────────────────╮
│ --base-level                         TEXT                  Base heading level      │
│                                                            relative to the         │
│                                                            template (accepts       │
│                                                            labels like             │
│                                                            "section").             │
│                                                            [default: 0]            │
│ --strip-heading     --keep-heading                         Drop the first document │
│                                                            heading from the        │
│                                                            rendered content.       │
│                                                            [default: keep-heading] │
│ --numbered           --unnumbered                          Toggle numbered         │
│                                                            headings.               │
│                                                            [default: numbered]     │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Template ─────────────────────────────────────────────────────────────────────────╮
│ --promote-title           --no-promote-title               Use the first heading as │
│                                                           the template title when  │
│                                                           metadata is missing.     │
│                                                           [default:                │
│                                                           promote-title]           │
│ --no-title                                                  Disable title           │
│                                                           generation even when     │
│                                                           metadata provides one.   │
│ --template            -t                            TEXT  Select a LaTeX template  │
│                                                           to use during            │
│                                                           conversion. Accepts a    │
│                                                           local path or a          │
│                                                           registered template      │
│                                                           name.                    │
│ --attribute           -a                            TEXT  Override template        │
│                                                           attributes as key=value  │
│                                                           pairs (e.g. -a           │
│                                                           emoji=color).            │
│ --slot                -s                            TEXT  Inject a document        │
│                                                           section into a template  │
│                                                           slot using               │
│                                                           'slot:Section'. Repeat   │
│                                                           to map multiple          │
│                                                           sections.                │
│ --bibliography        -b                            FILE  BibTeX files merged and  │
│                                                           exposed to the renderer. │
╰────────────────────────────────────────────────────────────────────────────────────╯

!!! note
    When `--build` is supplied without `--template`, TeXSmith falls back to the
    built-in `article` template. Pair `--template` with `--template-info` or
    `--template-scaffold` when you need to inspect or clone a non-default template.

╭─ Rendering ────────────────────────────────────────────────────────────────────────╮
│ --no-fallback-converters                                  Disable registration of  │
│                                                           placeholder converters   │
│                                                           when Docker is           │
│                                                           unavailable.             │
│ --copy-assets                 --no-copy-assets            Toggle copying of remote │
│                                                           assets to the output     │
│                                                           directory.               │
│                                                           [default: copy-assets]   │
│ --manifest                -m  --no-manifest     -M        Generate a manifest.json │
│                                                           file alongside the LaTeX │
│                                                           output.                  │
│                                                           [default: no-manifest]   │
│ --language                                          TEXT  Language code passed to  │
│                                                           babel (defaults to       │
│                                                           metadata or english).    │
│ --markdown-extensions     -x                        TEXT  Additional Markdown      │
│                                                           extensions to enable     │
│                                                           (comma or space          │
│                                                           separated values are     │
│                                                           accepted).               │
│ --disable-extension       -d                        TEXT  Markdown extensions to   │
│                                                           disable. Provide a comma │
│                                                           separated list or repeat │
│                                                           the option multiple      │
│                                                           times.                   │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Diagnostics ──────────────────────────────────────────────────────────────────────╮
│ --debug-html    --no-debug-html      Persist intermediate HTML snapshots (inherits │
│                                      from --debug when omitted).                   │
│ --debug-rules   --no-debug-rules     Display the ordered list of registered        │
│                                      renderer rules.                              │
│ --open-log      --no-open-log        Open the latexmk log with the system viewer   │
│                                      when compilation fails.                       │
│                                      [default: no-open-log]                        │
╰────────────────────────────────────────────────────────────────────────────────────╯
```


## TL;DR

### Simple conversion to LaTeX fragment

```text
$ texsmith hello.md
\chapter{Hello}\label{hello}

Hello, \textbf{world}! This is a sample \LaTeX{} document created with TeXSmith.
```

### Use a template

```text
$ texsmith hello.md -tarticle
    Template Conversion Summary
┌───────────────┬─────────────────┐
│ Artifact      │ Location        │
├───────────────┼─────────────────┤
│ Main document │ build/hello.tex │
└───────────────┴─────────────────┘

$ tree build
build
├── assets
├── callouts.sty
├── hello.tex
├── keystroke.sty
└── todolist.sty
```

### Compile a PDF

```text
$ uv run texsmith hello.md -tarticle --build
Using temporary output directory: /tmp/texsmith-czmi34j1
Running latexmk…
├─ Rc files read:
├─ This is Latexmk, John Collins, 31 Jan. 2024. Version 4.83.
├─ No existing .aux file, so I'll make a simple one, and require run of *latex.
├─ applying rule 'pdflatex'...
├─ Rule 'pdflatex':  Reasons for rerun
├─ Category 'other':
├─ Rerun of 'pdflatex' forced or previously required:
├─ Reason or flag: 'Initial setup'
├─ Run number 1 of rule 'pdflatex'
├─ Running 'lualatex --shell-escape  -interaction=nonstopmode -halt-on-error
-file-line-error -recorder  "hello.tex"'
├─ LuaHBTeX, Version 1.17.0 (TeX Live 2023/Debian)
├─ system commands enabled.
│  ├─ LaTeX2e <2023-11-01> patch level 1
│  ├─ L3 programming layer <2024-01-22>
│  │  ├─ article 2023/05/17 v1.4n Standard LaTeX document class
│  │  │     └─ For additional information on amsmath, use the `?' option.
│  ├─ *geometry* driver: auto-detecting
│  ├─ *geometry* detected driver: luatex
│  └─ f/fonts/map/pdftex/updmap/pdftex.map}]
├─ 1044 words of node memory still in use:
├─ 23 hlist, 2 vlist, 10 rule, 2 glue, 4 kern, 2 glyph, 60 attribute, 53 glue_s
├─ pec, 56 attribute_list, 2 write, 16 pdf_literal, 16 pdf_colorstack nodes
├─ avail lists: 1:2,2:169,3:29,4:27,5:84,6:12,7:460,8:1,9:96,10:2,11:18
├─ .otf>
├─ Output written on hello.pdf (1 page, 14946 bytes).
├─ Transcript written on hello.log.
├─ Getting log file 'hello.log'
├─ Examining 'hello.fls'
├─ Examining 'hello.log'
├─ Log file says output to 'hello.pdf'
├─ applying rule 'pdflatex'...
├─ Rule 'pdflatex':  Reasons for rerun
├─ Changed files or newly in use/created:
├─ hello.aux
├─ Run number 2 of rule 'pdflatex'
├─ Running 'lualatex --shell-escape  -interaction=nonstopmode -halt-on-error
-file-line-error -recorder  "hello.tex"'
├─ LuaHBTeX, Version 1.17.0 (TeX Live 2023/Debian)
├─ system commands enabled.
│  ├─ LaTeX2e <2023-11-01> patch level 1
│  ├─ L3 programming layer <2024-01-22>
│  │  ├─ article 2023/05/17 v1.4n Standard LaTeX document class
│  │  │     └─ For additional information on amsmath, use the `?' option.
│  ├─ *geometry* driver: auto-detecting
│  ├─ *geometry* detected driver: luatex
│  └─ f/fonts/map/pdftex/updmap/pdftex.map}]
├─ 1044 words of node memory still in use:
├─ 23 hlist, 2 vlist, 10 rule, 2 glue, 4 kern, 2 glyph, 60 attribute, 53 glue_s
├─ pec, 56 attribute_list, 2 write, 16 pdf_literal, 16 pdf_colorstack nodes
├─ avail lists: 1:2,2:169,3:29,4:27,5:84,6:12,7:460,8:1,9:96,10:2,11:18
├─ .otf>
├─ Output written on hello.pdf (1 page, 14946 bytes).
├─ Transcript written on hello.log.
├─ Getting log file 'hello.log'
├─ Examining 'hello.fls'
├─ Examining 'hello.log'
├─ Log file says output to 'hello.pdf'
└─ All targets (hello.pdf) are up-to-date
Summary — errors: 0, warnings: 0, info: 23
                   Build Outputs
┌───────────────┬──────────────────────────────────┐
│ Artifact      │ Location                         │
├───────────────┼──────────────────────────────────┤
│ Main document │ /tmp/texsmith-czmi34j1/hello.tex │
│ PDF           │ hello.pdf                        │
└───────────────┴──────────────────────────────────┘
```

## Positional Arguments

Positional arguments are detected automatically and merged the output. Supported input types are:

- One or more Markdown (`.md`, `.markdown`).
- HTML (`.html`, `.htm`) documents to convert. 
- BibTeX files (`.bib`, `.bibtex`) 

## Options

`--build`
:  Invoke `latexmk` after rendering to compile the resulting LaTeX project. Requires `--template`, and a TeX installation with `latexmk` available in `PATH`.

`--classic-output`
: When using `--build`, display raw `latexmk` output without parsing (use `--rich-output` for structured logs). Defaults to `--rich-output`.

`--legacy-latex-accents`
:   Escape accented characters and ligatures with legacy LaTeX macros instead of emitting Unicode glyph:

    ```tex
    é: \'{e}, à: \`{a}, ô: \^{o}, ü: \"{u}, æ: \ae{}, œ: \oe{}...
    ```

`--output/-o/--output-dir PATH`
: Destination for the rendered output. Pass a file path to write a single `.tex` file, a directory to emit `<stem>.tex` (and template artefacts), or omit the flag to print to `stdout` unless a template dictates otherwise. When not specified, the default is `stdout`.

`--isolate`
: Use a per-render TeX cache inside the output directory instead of the shared `~/.cache/texsmith` cache. This can be slower when using LuaTeX because of font reprocessing, but ensures reproducible builds.

## Managing slots

Slots are placeholders in the LaTeX template where specific document sections can be injected. Use the `--slot` (or `-s`) option to map input documents to these slots. For example, to inject `abstract.md` into the `abstract` slot:

```bash
texsmith docs/intro.md docs/chapter1.md \
  --template article \
  --output-dir build/book \
  --slot abstract:docs/abstract.md \
  main.md
```

You can also extract sections from a single document using the `slot:Section Name` syntax. For example, to inject the "Abstract" section from `main.md` into the `abstract` slot:"

```bash
texsmith docs/main.md \
  --template article \
  --output-dir build/book \
  --slot abstract:slot:Abstract
```

### Compile a PDF with `--build`

```bash
texsmith docs/manual.md \
  --template article \
  --output-dir build/pdf \
  --build
```

TeXSmith renders the template into `build/pdf`, sets up an isolated TeX cache, and executes `latexmk`. The resulting `manual.pdf` is reported in the build summary.

Need deterministic logs (for CI or scripting)? Switch to classic output:

```bash
texsmith docs/manual.md \
  --template article \
  --output-dir build/pdf \
  --build \
  --classic-output
```

TeXSmith merges all BibTeX sources and only writes the references that are cited in the document.
