# Development Notes

Roadmap and development notes for TeXSmith. I keep this file as a running checklist of features to implement, refactorings to perform, and documentation to write. It will remain part of TeXSmith until version 1.0.0 ships.

## Roadmap

- [x] Test for multi document builds (`texsmith a.md b.md c.md`)
- [x] Only load ts-callouts si des callouts are used
- [x] Only load ts-code si du code est utilisé
- [x] Only load ts-glossary si une glossary est utilisée
- [x] Only load ts-index si une index est utilisée
- [x] Demonstrate glossary in book
- [x] Support glossaries (glossaries package)
- [x] csquote
- [ ] Manage title fragment to insert title meta
- [ ] Manage fragments order from before/after hooks instead of in fragments.py
- [ ] tocloft
- [ ] multicol
- [ ] enumitem
- [ ] Snippet (frame dog ear would be good in the build pdf)
- [ ] Be verbose in mkdocs show what happens (fetching assets, building...)
- [ ] docs/syntax/captions.md (captions not working when using texsmith?)
- [ ] Never use user cache. Always use a .cache local?
- [ ] Make CI pass
- [ ] Demonstrate multi indexes (dates, ...)
- [ ] Build snippet with pdflatex when possible (faster)
- [ ] Complete docstring coverage across the project
- [ ] Support cross-references (cleveref package)
- [ ] Provide listings/verbatim/minted handling
- [ ] Add table width controls (auto, fixed width, `tabularx`, `tabulary`, etc.)
- [ ] Support table orientation (rotate very wide tables)
- [ ] Scaffold templates with Cookiecutter
- [ ] Implement `texsmith template create my-template`
- [ ] Offer compilation with Docker or TeX Live (user choice)
- [ ] Deploy to PyPI
- [ ] Epigraph Plugin
- [ ] Sidenotes (`marginpar` package with footnotes syntax)
- [ ] Letterine
- [ ] uv run mkdocs build #--strict not yet ready

## Book Template Integration with MkDocs

Update the book template integration:

- [ ] Use the default Mermaid configuration (no color overrides).
- [ ] Build MkDocs with parts at level 0.
- [ ] Hide the list of tables when no tables exist.

## .texsmith/config.toml

Improve the documentation and structure for user configuration. The goal is to let users pick default templates, Mermaid styles, preferred options, and paper formats for everyday TeXSmith usage. The file is optional and can live in the current directory or any parent directory. When present, the `.texsmith` folder also stores cache, configuration, and other user-specific data.

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

## Arabic

We can allow environment to support specific languages:

```markdown
::: language arabic
قِفا نَبْكِ مِنْ ذِكرَى حبيبٍ ومَن
:::
```

This will trigger the inclusion of `polyglossia` and set up the Arabic environment. We could also set fonts automatically based on the language. For Arabic, we can use the `Amiri` font as follows:

```latex
\documentclass[a4paper]{article}

\usepackage{fontspec}
\usepackage{polyglossia}
\usepackage{ts-fonts}
\setmainlanguage{english}
\setotherlanguage{arabic}

\newfontfamily\arabicfont[Script=Arabic]{Amiri}

\begin{document}

\begin{Arabic}
قِفا نَبْكِ مِنْ ذِكرَى حبيبٍ ومَنزِلِ
بِسِقطِ اللِّوَى بَيْنَ الدَّخول فَحَوْمَلِ
فَتُوضِحَ فَالمِقراةِ لَم يَعفُ رَسمُها
لِما نَسَجَتها مِن جَنُوبٍ وشَمألِ
تَرَى بَعَرَ الأرْآمِ في عَرَصاتِها
وَقِيْعانِها كَأنَّهُ حَبُّ فُلْفُلِ
\end{Arabic}

\end{document}
```

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

Integrate epigraph support via a dedicated plugin. The goal is to let users insert epigraphs easily from Markdown files. It can be declared as a fragment and declared into the document via frontmatter:

```yaml
epigraph: text
epigraph:
  quote: "To be, or not to be, that is the question."
  source: "William Shakespeare, Hamlet"
```

This is inserted into the LaTeX output using the `epigraph` package:

```latex
\usepackage{epigraph}
\setlength\epigraphwidth{0.6\textwidth}
\setlength\epigraphrule{0pt}
```

Then, at the desired location in the document:

```latex
\epigraph{To be, or not to be, that is the question.}{William Shakespeare, \textit{Hamlet}}
```

### Svgbob

This can be a good example of a standalone TeXSmith plugin that allows rendering ASCII art diagrams using SvgBob.

[Svgbob](https://github.com/ivanceras/svgbob) lets you sketch diagrams using ASCII art. Save the source with a `.bob` extension (or keep it inline) and link to it like any other image:

```markdown
![Sequence diagram](assets/pipeline.bob)
```

During the build TeXSmith calls the bundled Svgbob converter, generates a PDF, and inserts it into the final LaTeX output. Cached artifacts prevent repeated rendering when the source diagram stays the same.

SVGBob can be installed on Ubuntu via:

```bash
cargo install svgbob_cli
```

It is installed by default into `svgbob_cli` or `~/.cargo/bin/svgbob_cli` we want to fetch both warn if the binary is missing and also allow users to override the path via configuration.

We can insert the image in both way:

````markdown
```svgbob
       +10-15V           ___0,047R
      *---------o-----o-|___|-o--o---------o----o-------.
    + |         |     |       |  |         |    |       |
    -===-      _|_    |       | .+.        |    |       |
    -===-      .-.    |       | | | 2k2    |    |       |
    -===-    470| +   |       | | |        |    |      _|_
    - |       uF|     '--.    | '+'       .+.   |      \ / LED
      +---------o        |6   |7 |8    1k | |   |      -+-
             ___|___   .-+----+--+--.     | |   |       |
              -═══-    |            |     '+'   |       |
                -      |            |1     |  |/  BC    |
               GND     |            +------o--+   547   |
                       |            |      |  |`>       |
                       |            |     ,+.   |       |
               .-------+            | 220R| |   o----||-+  IRF9Z34
               |       |            |     | |   |    |+->
               |       |  MC34063   |     `+'   |    ||-+
               |       |            |      |    |       |  BYV29     -12V6
               |       |            |      '----'       o--|<-o----o--X OUT
 6000 micro  - | +     |            |2                  |     |    |
 Farad, 40V ___|_____  |            |--o                C|    |    |
 Capacitor  ~ ~ ~ ~ ~  |            | GND         30uH  C|    |   --- 470
               |       |            |3      1nF         C|    |   ###  uF
               |       |            |-------||--.       |     |    | +
               |       '-----+----+-'           |      GND    |   GND
               |            5|   4|             |             |
               |             |    '-------------o-------------o
               |             |                           ___  |
               `-------------*------/\/\/------------o--|___|-'
                                     2k              |       1k0
                                                    .+.
                                                    | | 5k6 + 3k3
                                                    | | in Serie
                                                    '+'
                                                     |
                                                    GND
```
````

If not available svgbob diagrams can be skipped with a warning and the diagram is rendered as a code block.

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

## Issues

### Acronyms multiline

Thw following don't work, it should either warn or join the different lines together.

```markdown
# Acronyms

The National Aeronautics and Space Administration NASA is responsible for the
civilian space program.

*[NASA]:
    Line 1
    Line 2
```

### Font style with mono

We want to support combinations of font styles with the monospace font. For example:

```markdown
*`abc`*
***`abc`***
__*`abc`*__
```

In this case the `code inline` is treated as `texttt` with the proper escapes.

### Center/Right alignment

```md
::: center
texte
:::

::: right
texte
:::
```

### Fences the gros bordel

#### Code

We only use `` ``` `` fences for code blocks or other special blocks like mermaid, latex, custom tables, etc. No other uses should be allowed.

#### Admonitions

We prefer the MkDocs admonition syntax as it is more flexible and better supported.

```md
!!! note "Note Title"

    This is the content of the note.

??? info "Folddable Info Title"

    This is the content of the info.
```

#### Fenced custom

The `:::` syntax is reserved for custom containers like `center`, `right`, `language`, etc. No other uses should be allowed.

```text
::: align center
This text is centered.
:::

::: align right
This text is right-aligned.
:::

::: language arabic
```

We use the syntax `verb` + `option` after the opening `:::` to specify the type of container and any relevant options.

```text
::: latex only
This LaTeX-only content will be included in the LaTeX output but ignored in HTML.
:::

::: html only
This HTML-only content will be included in the HTML output but ignored in LaTeX.
:::
```

We can use raw LaTeX blocks for more complex LaTeX content that doesn't fit well in Markdown:

```text
::: latex raw
\clearpage
:::
```

With SuperFences we support extra HTML attributes for custom containers:

```text
::: language arabic {#custom-id .custom-class data-attr="value"}
This is Arabic content with custom HTML attributes.
:::
```

Each `:::` container is converted into a `<div>` with the specified attributes in HTML, while LaTeX processes the content according to the container type.

#### GFM Support for admonitions

We want TeXSmith to support GitHub Flavored Markdown (GFM) admonitions as well. This includes the ability to create notes, warnings, tips, and other types of admonitions using the GFM syntax.

```md
> [!NOTE]
> This is a note admonition.
```

This is converted to the exact same output as the MkDocs admonition syntax. It is equivalent to:

```md
!!! note
    This is a note admonition.
```
