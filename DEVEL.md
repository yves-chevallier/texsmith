# Development Notes

Roadmap and development notes for TeXSmith. I keep this file as a running checklist of features to implement, refactorings to perform, and documentation to write. It will remain part of TeXSmith until version 1.0.0 ships.

## Roadmap

- [x] Extract template aggregation into TemplateRenderer and keep TemplateSession slim
- [x] Replace `safe_quote` with `requote_url` from `requests.utils`
- [x] Replace helper functions with the `latexcodec` package
- [x] Replace `to_kebab_case` with `python-slugify`
- [x] Document `RenderPhase(Enum)` and explain each state
- [x] Support the configured language (babel already, polyglossia next)
- [x] Allow Renderer and formatter extensions (demo counter)
- [x] Support index generation (makeindex, xindy)
- [x] Rename the `texsmith` package and every `texsmith-template-*` template
- [x] Enable all common extensions by default
- [x] Support bibliographies (biblatex, natbib, etc.)
- [x] Support footnotes
- [x] Convert selected journal templates
- [x] Add CLI and MkDocs unit and integration tests
- [x] Support images (and convert to PDF when required)
- [x] Manage figure captions
- [x] Manage table captions
- [x] Allow slots to be defined in the frontmatter
- [x] Provide a robust Docker submodule/class
- [x] Declare solution/exercise workflows through plugins
- [x] Add more Markdown extensions (definition lists, tables, etc.)
- [x] Support draw.io assets (.drawio, .dio)
- [x] Support inline Mermaid
- [x] Support `.mmd`, `.mermaid`, and remote Mermaid definitions (e.g., `https://mermaid.live/edit#...`)
- [x] Add Twemoji emoji support
- [x] Ensure images render across formats (.tiff, .webp, .avif, .gif, .png, .bmp, etc.)
- [x] Provide a verbose CLI with clear warnings and errors
- [x] Add a `--debug` flag that shows full exceptions
- [x] Build bibliographies from DOI references in the frontmatter
- [x] Improve performance by converting HTML to XML and using lxml instead of htmlparser
- [x] Support multiple input pages (multiple Markdown or HTML files)
- [x] Improve error handling and reporting during LaTeX compilation
- [x] Support raw LaTeX blocks (optionally hidden from HTML)
- [x] Create CI/CD pipelines
- [x] Add the `texsmith --template book --template-info` command
- [x] Manage figure references (`\cref`, etc.)
- [x] Optimize bibliography management using `.bib` files instead of Jinja
- [x] Document how to create custom LaTeX templates
- [x] Support hashtag indexes through the built-in `texsmith.index` extension
- [x] Add `\textsc` support in Markdown
- [x] Provide Noto Color Emoji or `{\fontspec{Symbola}\char"1F343}` fallbacks (color and monochrome)
- [x] Ensure all examples build successfully
- [x] Write documentation
- [x] Generate assets as SHA only when using MkDocs (or when a specific option requires it)
- [x] Fix or test `__text__` inside admonitions
- [x] Base the letter template on KOMA `scrlttr2` and adjust country-specific defaults
- [x] Add an article template as the TeXSmith "default"
- [x] Finalize index generation workflow
- [x] Add progress-bar support
- [x] Integrate coverage reporting
- [x] Snippet Template
- [x] Snippet plugin
- [x] Integrate Nox
- [ ] Snippet plugin, avoid rebuilding unchanged snippets
- [ ] Epigraph Plugin
- [ ] Consolidate Book template
- [ ] Put fonts and code into separate sty merged during build
- [ ] Avoid `--shell-escape` when `minted` is unused (no code blocks or inline code)
- [ ] Dynamically update the engine in `latexmkrc` (pdflatex, xelatex, lualatex)
- [ ] Support glossaries (glossaries package)
- [ ] Support cross-references (cleveref package)
- [ ] Provide listings/verbatim/minted handling
- [ ] Add table width controls (auto, fixed width, `tabularx`, `tabulary`, etc.)
- [ ] Support table orientation (rotate very wide tables)
- [ ] Scaffold templates with Cookiecutter
- [ ] Implement `texsmith template create my-template`
- [ ] Offer compilation with Docker or TeX Live (user choice)
- [ ] Complete docstring coverage across the project
- [ ] Deploy to PyPI

## Book Template Integration with MkDocs

Update the book template integration:

- [x] Remove the HEIG-VD reference.
- [x] Remove the optional cover page.
- [ ] Use classic admonitions.
- [ ] Use Noto for code samples.
- [ ] Decide on a serif vs. sans-serif body font.
- [ ] Inherit code styling from the article template (smaller arc and thinner frame).
- [ ] Use the default Mermaid configuration (no color overrides).
- [ ] Avoid French typographic conventions.
- [ ] Build MkDocs with parts at level 0.
- [ ] Hide the list of tables when no tables exist.

## Sortir sty des templates

Dans les templates plugins on a

```latex

\usepackage{microtype}

\BLOCK{ if latex_engine == "lualatex" or latex_engine == "xelatex" }
\usepackage{fontspec}
\BLOCK{ else }
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\BLOCK{ endif }

\BLOCK{ if latex_engine == "lualatex" }
\BLOCK{ set base_font_fallbacks = [
    "NotoColorEmoji:mode=harf;",
    "NotoNaskhArabic:mode=harf;",
    "NotoSerifHebrew:mode=harf;",
    "NotoSerifDevanagari:mode=harf;",
    "NotoSerifTamil:mode=harf;",
    "NotoSerifTibetan:mode=harf;",
    "NotoSerifCJKkr:mode=harf;",
    "NotoSans:mode=harf;",
    "NotoSansSymbols2-Regular:mode=harf;",
    "NotoSansMath-Regular:mode=harf;",
    "NotoMusic-Regular:mode=harf;",
    "NotoSansSyriac-Regular:mode=harf;",
    "NotoSansSyriacWestern-Regular:mode=harf;"
] }
\BLOCK{ set fallback_fonts = base_font_fallbacks + (extra_font_fallbacks or []) }
\directlua{luaotfload.add_fallback
  ("fontfallback",
  {
      \BLOCK{ for font in fallback_fonts }
      "\VAR{font}"\BLOCK{ if not loop.last },\BLOCK{ endif }
      \BLOCK{ endfor }
  }
  )}

\setmainfont{Latin Modern Roman}[
  Ligatures=TeX,
  SmallCapsFont = Latin Modern Roman Caps,
  RawFeature = {fallback=fontfallback},
]

\setsansfont{Latin Modern Sans}[
  RawFeature={fallback=fontfallback}
]

\setmonofont{FreeMono}[
  Scale=0.9,
  ItalicFont={* Oblique},
  BoldFont={* Bold},
  BoldItalicFont={* Bold Oblique},
  RawFeature={fallback=fontfallback}
]
```

## .texsmith/config.toml

Improve the documentation and structure for user configuration. The goal is to let users pick default templates, Mermaid styles, preferred options, and paper formats for everyday TeXSmith usage. The file is optional and can live in the current directory or any parent directory. When present, the `.texsmith` folder also stores cache, configuration, and other user-specific data.

## latexmkrc Integration

Always generate a `latexmkrc` for every template to simplify builds. Running `latexmk` should build the right file with the right engine, enabling `--shell-escape` only when needed (for instance when `minted` is in use). Avoid injecting minted-specific logic when no code blocks exist.


### Glossary

The MkDocs [ezglossary](https://realtimeprojects.github.io/mkdocs-ezglossary) plugin exists, but the syntax is unintuitive (for example, the semicolon separator) and does not handle spaced or formatted entries well. Ideally, readers should be able to access the glossary as a popup, tooltip, or link.

LaTeX glossaries usually rely on the `glossaries` package and definitions declared in the preamble via `\newglossaryentry`:

```latex
\newglossaryentry{key}{
  name={singular form},
  plural={plural form},
  description={descriptive text},
  first={special form for first use},
  text={normal form (if you want to force it)},
}
```

`\gls` uses the standard form, `\Gls` capitalizes the first letter, `\glspl` gives the plural, and `\Glspl` capitalizes the plural. The first use of the term falls back to the `first` form when present, otherwise `name`. Markdown alone cannot express all of that. One option is to define glossary entries in frontmatter:

```yml
glossary:
  html:
    name: HTML
    plural: HTMLs
    description: >
      HyperText Markup Language, the standard markup language for
      documents designed to be displayed in a web browser.
    first: HyperText Markup Language (HTML)
```

Place an anchor where the term is defined:

```markdown
The **HTML**{#gls-html} is the standard markup language for web pages...
```

### Acronyms

Acronyms often live alongside glossary entries:

```tex
\newglossaryentry{key}{
  name={singular form},
  plural={plural form},
  description={descriptive text},
  first={special form for first use},
  text={normal form (if you want to force it)},
}

\newacronym{gcd}{GCD}{greatest common divisor}
```

Use `\gls` for the nominal form, `\Gls` to capitalize the first letter, `\glspl` for the plural, and `\Glspl` for the capitalized plural. `\acrshort` forces the short form, `\acrlong` forces the long form, and `\acrfull` prints “Long Version (LV)”. HTML typically leans on `<abbr>` for similar semantics.

### Abbreviations

Support abbreviations end-to-end. If partial functionality already exists, refactor it as follows:

1. Capture all `<abbr>` entries in the document.
2. Warn when a term reuses different descriptions.
3. Translate abbreviations to LaTeX via `\acrshort{term}`.
4. Expose an `acronyms` attribute to the template, structured like `{ 'key': ('term', 'description'), ... }`.
5. Have Jinja loop over `acronyms` and emit `\newacronym{key}{term}{description}` when the list is not empty.
6. Conditionally include `\usepackage[acronym]{glossaries}` and `\makeglossaries` in the templates.

## Complex Tables

Markdown offers limited table configuration—only column alignment by default. PyMdown provides captions, and superfences can inject more metadata, but we still miss:

- Table width (auto vs. full width)
- Resizing oversized tables
- Orientation (portrait vs. landscape)
- Column and row spanning
- Horizontal and vertical separator lines
- Column widths (fixed, auto, relative)

### Extended Markdown Table Syntax

Leverage Pymdown’s table extension to add more metadata directly in Markdown. For example:
texsmith.spantable extension lets us span cells in standard Markdown tables.

The `>>>` syntax will span cells horizontally, the `vvv` syntax will span cells vertically.

```markdown
| Header 1 | Header 2 | Header 3 |
|:---------|:--------:|---------:|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | >>>      | Cell 6   |
| Cell 7   | Cell 8   | Cell 11  |
| Cell 9   |          | vvv      |
```

### Raw table syntax

Superfences do not work directly with tables, so define a `table` fence that accepts YAML options:

````markdown
```table
width: full
caption: Sample Table
label: tbl:sample
header: true
print:
  orientation: landscape
  resize: true
columns:
  - alignment: left
    width: auto
  - alignment: center
    width: 2cm
  - alignment: right
    width: auto
rows:
  - height: auto
    alignment: top
    span: [2, auto]
data:
  - [Cell 1, Cell 2, Cell 3]
  - [Cell 4, null, Cell 6]
  - [Cell 7, Cell 8, null]
```
````

The goal is to convert Markdown tables into LaTeX tables with automatic line breaks so that columns wrap gracefully when a table is too wide.

## Figure References

Printed references depend on the document language. In English we would write, “The elephant shown in Figure 1 is large.” The LaTeX equivalent is `The elephant shown in Figure~\ref{fig:elephant} is large.` Pymdown lets us write:

```markdown
The elephant shown in figure [#fig:elephant] is large.
```

```latex
\hyperref[fig:elephant]{Figure~\ref*{fig:elephant}}

\usepackage[nameinlink]{cleveref}
The elephant shown in \Cref{fig:elephant} is large.
The same sentence in French typography would translate to “The elephant shown in \cref{fig:elephant} is large,” keeping “figure” lowercase.
```

In scientific English we capitalize “Figure”, while French typography keeps “figure” lowercase.

## Standalone Plugins

### Epigraph

Integrate epigraph support via a dedicated plugin. The goal is to let users insert epigraphs easily from Markdown files.

### Svgbob

This can be a good example of a standalone TeXSmith plugin that allows rendering ASCII art diagrams using SvgBob.

[Svgbob](https://github.com/ivanceras/svgbob) lets you sketch diagrams using ASCII art. Save the source with a `.bob` extension (or keep it inline) and link to it like any other image:

```markdown
![Sequence diagram](assets/pipeline.bob)
```

During the build TeXSmith calls the bundled Svgbob converter, generates a PDF, and inserts it into the final LaTeX output. Cached artifacts prevent repeated rendering when the source diagram stays the same.

### CircuitTikZ

The [CircuitTikZ designer](https://circuit2tikz.tf.fau.de/designer/) helps produce circuit diagrams from the browser. Export the generated TikZ snippet and wrap it in a raw LaTeX fence:

````markdown
```latex { circuitikz }
\begin{circuitikz}
    \draw (0,0) to[battery] (0,2)
          -- (3,2) to[R=R] (3,0) -- (0,0);
\end{circuitikz}
```
````

Raw blocks bypass the HTML output but remain in the LaTeX build. To keep the TikZ code in a separate file, include it via `\input{}` inside a raw fence and store the `.tex` asset alongside the Markdown.

## Module Design Principles

Verify that TeXSmith respects these design principles:

- Modules can inject, extend, and redefine functionality.
- Modules remain deterministic through topological ordering.
- Modules foster reusability and remixing.
- Modules cooperate through well-defined contracts.

## Visual Tweaks

- Reduce line height for code that uses Unicode box characters.
- Restyle inserted text (currently green and overly rounded); see “Formatting inserted text”.
- `{~~deleted text~~}` should drop the curly braces, which currently leak into the output.

## MkDocs Linking Issues

MkDocs currently fails to resolve links to other pages. For example, `[High-Level Workflows](api/high-level.md)` becomes `\ref{snippet:...` but the referenced snippet is never defined. Replacing the syntax with `\ref` builds successfully but still fails at runtime. Investigate and fix the resolver so links work throughout the site.

Also note that the scientific paper “cheese” example prematurely closes code blocks after a snippet. Identify why the snippet terminates early and correct it.

## Markdown Package Issues

`mkdocstrings` autorefs define heading anchors via `[](){#}`, which triggers Markdown lint violations. Find a syntax or lint configuration that avoids false positives.

## Lint/Format

We still need a lint/format solution that plays nicely with MkDocs syntax; existing tools fall short.
