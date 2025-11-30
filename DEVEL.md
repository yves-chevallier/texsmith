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
- [x] Emojis without svg conversions
- [x] two columns in article template
- [x] Provide listings/verbatim/minted handling
- [x] Add support for Tectonic engine
- [x] Download tectonic automatically if not installed
- [x] Download biber automatically if not installed
- [x] Add support for Makefile deps `.d` files
- [x] Include fonts in package (like OpenMoji and Noto Color Emoji)
- [x] Remove enhanced log for tectonic
- [ ] Configure style for code highlight pygments default is bw
- [ ] Snippet template
- [ ] Drawio Exporter remote via wreight... see in scripts
- [ ] Mermaid color configuration for MkDocs
- [ ] Global user's configuration (.texsmith/config.yml)
- [ ] Acronyms multiline
- [ ] MkDocs Linking Issues
- [ ] Font style with mono
- [ ] Unified Fences Syntax
  - [ ] Multicolumns
  - [ ] Font Size
  - [ ] Center/Right alignment
  - [ ] Language
  - [ ] LaTeX only / HTML only
  - [ ] LaTeX raw
- [ ] Clean book template
- [ ] Add example: university exam
- [ ] Add engine through Docker (docker-tectonic, docker-texlive)
- [ ] Use docker tectonic if tectonic is not installed
- [ ] Integrate docker docker run -v $(pwd):/usr/src/tex  dxjoke/tectonic-docker tectonic book.tex
- [ ] Build MkDocs with parts at level 0.
- [ ] Hide the list of tables when no tables exist.
- [ ] Manage title fragment to insert title meta
- [ ] Manage fragments order from before/after hooks instead of in fragments.py
- [ ] tocloft
- [ ] enumitem
- [ ] Fix snippet template (frame dog ear would be good in the build pdf)
- [ ] Be verbose in mkdocs show what happens (fetching assets, building...)
- [ ] docs/syntax/captions.md (captions not working when using texsmith?)
- [ ] Use env var for TEXSMITH_CACHE, default to ~/.texsmith/cache
- [ ] Make CI pass
- [ ] Support for multi-indexes (dates, ...)
- [ ] Complete docstrings in the codebase for better mkdocstrings generation
- [ ] Support cross-references (cleveref package)
- [ ] Add table width controls (auto, fixed width, `tabularx`, `tabulary`, etc.)
- [ ] Support table orientation (rotate very wide tables)
- [ ] Scaffold templates with Cookiecutter
- [ ] Implement `texsmith template create my-template`
- [ ] Offer compilation with Docker or TeX Live (user choice)
- [ ] Deploy to PyPI
- [ ] CI: uv run mkdocs build #--strict not yet ready
- [ ] Windows Support
- [ ] Insert Examples PDFs in the GitHub Releases
- [ ] Develop submodules as standalone plugins
  - [ ] Marginalia (`marginpar` package with footnotes syntax)
  - [ ] Epigraph Plugin
  - [ ] Letterine
  - [ ] Custom variables to insert in a document using moustaches


- [ ] Simplify the attributes SSOT for templates and fragments

- [ ] Implement drawio over pywreight
- [ ] ts-languages that uses polyglossia and specific things to languages

## Refactoring fonts management

We implemented a lot of code related to fonts management, and we want to refactor the whole because it is unstable and hard to maintain. The goal is to have a clear and simple way to add support for new languages and scripts, with the right font selection strategy.

We will use `unicode-blocks-py` to detect the scripts used in the document. During LaTeX translation, we parse the document to detect all the scripts used. For each script we define a strategy to select the right fonts to use. We will wrap to the latex text wither the inline `\text<language>{...}` or the environment `\begin{<language>} ... \end{<language>}` depending on the script. Unicode blocks will help to detect with `unicode-blocks.of(char)` the script of each character. To spped up the process we only match with a regex the characters outside the basic latin range and query unicode-blocks for those caracters. The goal is to detect the sequences of characters in the same script and wrap them with the right LaTeX commands.

The strategy for each script can be one of the following:

- Polyglossia
- XeCJK / LuaCJK
- Manual

We try to let to use CTAN packages when possible for collecting the fonts.

Pour les emojis on pointe sur Noto Color Emoji ou OpenMoji-black-glyf.ttf si on veut du noir et blanc:

In [7]: unicode_blocks.of('⚡')
Out[7]: UnicodeBlock(name='Miscellaneous Symbols', start=0x2600, end=0x26ff, assigned_ranges=[(0x2600, 0x26ff)], aliases=['MISCSYMBOLS'])

In [8]: unicode_blocks.of('👩')
Out[8]: UnicodeBlock(name='Miscellaneous Symbols and Pictographs', start=0x1f300, end=0x1f5ff, assigned_ranges=[(0x1f300, 0x1f5ff)], aliases=['MISCPICTOGRAPHS'])

In [9]: unicode_blocks.of('💻')
Out[9]: UnicodeBlock(name='Miscellaneous Symbols and Pictographs', start=0x1f300, end=0x1f5ff, assigned_ranges=[(0x1f300, 0x1f5ff)], aliases=['MISCPICTOGRAPHS'])

### ts-fonts.jinja.sty

This file became a huge mess. We want to simplify ans still support all the engines: pdflatex, xelatex, lualatex, tectonic. You can get inspiration from this file but we want to rewrite it correctly SOLID and KISS.

### Manual Strategy

The `ts-fonts` fragment will add the necessary LaTeX code to define the fonts for each language/script. For example, for Kannada, Malayalam, and Burmese/Myanmar we can define:

```latex
% Kannada
\newfontfamily\kannadafont[Script=Kannada]{Noto Sans Kannada}
\newcommand{\textkannada}[1]{{\kannadafont #1}}
\newenvironment{kannada}{\kannadafont}{}

% Malayalam
\newfontfamily\malayalamfont[Script=Malayalam]{Noto Sans Malayalam}
\newcommand{\textmalayalam}[1]{{\malayalamfont #1}}
\newenvironment{malayalam}{\malayalamfont}{}

% Burmese / Myanmar
\newfontfamily\burmesefont[Script=Myanmar]{Noto Sans Myanmar}
\newcommand{\textburmese}[1]{{\burmesefont #1}}
\newenvironment{burmese}{\burmesefont}{}
```

### Case of CJK languages

For Chinese, Japanese, and Korean we can use the `xeCJK` or `luaCJK` package depending on the engine. We define the fonts for each language:

```latex
\ifLuaTeX
\usepackage{luatexja-fontspec}
\setmainjfont{Noto Serif CJK JP} %if japanese is used
\setsansjfont{Noto Sans CJK JP} % if japanese is used
\newjfontfamily\krjfont{Noto Sans CJK KR} % If korean is used
\else
\usepackage{xeCJK}
\setCJKmainfont{Noto Serif CJK JP}
\setCJKsansfont{Noto Sans CJK JP}
\newCJKfontfamily\krfont{Noto Sans CJK KR}
\fi
```

### Polyglossia

To support latin and some cyrillic based languages we can use polyglossia. For example for Vietnamese:

```latex
\usepackage{polyglossia}
\setmainlanguage{english} % Depends ont he language attribute for the document
\setotherlanguage{vietnamese} %Which uses extended latin characters
```

We use polyglossa strategy if compatible with it.

### Font Download

We will use the NotoFallback class to download the necessary fonts based ont the metadata defined for each script/language.
This class will use the `scripts/generate_noto_dataset.py` that helps to match unicode blocks to Noto fonts. We can improve the dataset or suppress unused features to
leverage the use of `unicode-blocks` to identify the script then have a correspondance to the Noto font to use.

### Preamble context contracts

- `_script_usage` records every detected script with the strategy to use (Polyglossia vs CJK vs manual). Fragments such as `ts-fonts` must no longer scan slot content to guess languages.
- `emoji_spec` mirrors the emoji resolver output: `mode`, `font_family`, `font_path`, and `color_enabled`. Templates should rely on that object instead of recomputing preferences.
- `fallback_fonts`, `unicode_font_classes`, and `script_fallbacks` are final, filtered lists prepared by the manager; fragments must not inject defaults.

### LuaLaTeX

For LuaLaTeX we only relies on the fallback mechanism.


## Configure highlight style for code blocks and code inlines

We currently use pygments internally or use minted package to highlight code blocks and inline code. We want to allow users to configure the style used for highlighting code. For example, we can use the `bw` style for black and white output, or `tango` for colored output. This configuration from the frontmatter (press namespace in md files) with `code.style=bw` by default.

Can you do this for all methods except listings?


## Makeindex with engine tectonic

With the engine `tectonic`, makeindex is not called automatically same for bibtex and makeglossaries. The goal is to implement that in TeXSmith. If the document uses an index, a glossary, or a bibliography, TeXSmith should call the appropriate tools between compilation passes.
And rerun the compilation until all references are resolved.

For the tools for index we look for `texindy` or `makeindex` in this order. The first one found is used.

## Issues

- [ ] warning: Expected 'fonts/OpenMoji-black-glyf.ttf' in archive but found 'OpenMoji-black-glyf/OpenMoji-black-glyf.ttf'. Using the available font file instead.
- [ ] ├─ ▲ There is no ���� (U+1F4DD) in font [./fonts/lmsans10-bold.otf]/OT:script=latn;language=dflt;mapping=tex-text;! L'exemple admonition n'utilise pas les bonnes fonts pour les emojis, elle nes sont pas cosidérées, le répertoire fonts de l'output n'est pas pris encompte ?
- [ ] TeXGyre to be added to the list of fonts to download
- [ ] Multidocument uses /usr/share fonts, not local ones ? Should download local ones
- [ ] Cookingsymbols not availble in tectonic ?

### Color emoji don't work with Tectonic/XeLaTeX

Il faudrait que XeTeX (ou un XeTeX 2.0) intègre un moteur de rendu qui gère vraiment les polices couleur (COLR/CPAL, CBDT/CBLC, SVGinOT) et sache les convertir en quelque chose de compatible PDF.

## Features

### Include Fonts in Package


examples/abbr make still fails due to DNS/network outages: OpenMoji downloads blocked and Tectonic can’t fetch TeX packages (makeidx.sty, bundle tarballs). Once network access is available (or the TeX bundle is preinstalled/cached), the build should proceed without the twemoji.sty error because emoji fallback now uses SVG images



Certaines fonts utilisées par TeXSmith comme OpenMoji-black-glyf.ttf sont difficile à trouver et télécharger. Il faudrait les intégrer dans le package TeXSmith pour éviter aux utilisateurs d'avoir à les chercher et les installer eux-mêmes. Elles seront copiées dans le dossier de build si utilisées. On commence juste par cette font pour l'instant.

Si utilisé, télécharger https://github.com/googlefonts/noto-emoji/raw/refs/heads/main/fonts/NotoColorEmoji.ttf la garder en cache dans ~/.texsmith/fonts/NotoColorEmoji.ttf et la copier dans le dossier de build si utilisé.

Pour openmoji télécharger depuis https://github.com/hfg-gmuend/openmoji/releases/latest/download/openmoji-svg-black.zip
extraire le zip et prendre la font `fonts/OpenMoji-black-glyf.ttf` la garder en cache dans ~/.texsmith/fonts/OpenMoji-black-glyf.ttf et la copier dans le dossier de build si utilisé.

Si pas possible de télécharger les fonts, afficher un warning et fallback sur les emojis via images svg de twemoji.

### Mermaid color configuration

Je remarque que les diagrammes mermaid qui sont créés apparaissent avec un fond gris dans le pdf. Mais nous avions configuré un style mermaid global a texsmith pour avoir des diagrammes b&w dans le pdf final. Il n'est probablement plus activé ou pris en compte. Il faut vérifier cela et corriger le problème.

La gestion du cache des assets est aussi à vérifier et la rendre dépendante de la configuration mermaid (si on change le style, il faut regénérer les diagrammes), ou alors si l'exécutable ou la version de l'image docker utilisée change.

On ajoute ausis cette vérification pour les assets drawio.

### Global user's configuraiton (.texsmith/config.yml)

We want texsmith to support a global user configuration file located at `.texsmith/config.yml`. This file allows users to set their preferred defaults for templates, Mermaid styles, compilation options, and paper formats. The configuration file is optional and can be placed in the current working directory or any parent directory.

This does only affect the CLI usage of TeXSmith. The API still remains robust and does not depend on any global configuration, except for the cache directory.

A config file could be:

```yaml
template: article
engine: tectonic
paper:
  format: a4
  orientation: portrait
mermaid:
  theme: neutral
callouts:
  style: fancy
```

The format is not rigidly defined. It is used to set default values for command-line options. Command-line options always take precedence over configuration file settings and YAML front matter in Markdown files have the highest precedence.

Fragments and plugins, and everything inherit from this global configuration when using the CLI.

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

### MkDocs Linking Issues

MkDocs currently fails to resolve links to other pages. For example, `[High-Level Workflows](api/high-level.md)` becomes `\ref{snippet:...` but the referenced snippet is never defined. Replacing the syntax with `\ref` builds successfully but still fails at runtime. Investigate and fix the resolver so links work throughout the site.

Also note that the scientific paper “cheese” example prematurely closes code blocks after a snippet. Identify why the snippet terminates early and correct it.

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

##### Font Size

> tiny, small, large, huge, enormous
> Other synonyms: tiny, scriptsize, footnotesize, small, normalsize, large, Large, LARGE, huge, Huge
> Other english synonyms: tiny, very small, small, normal, big, very big, huge, enormous

| Adjective(s) (EN)     | LaTeX                   | HTML correspondance (CSS)                  |
|-----------------------|-------------------------|--------------------------------------------|
| tiny, very tiny       | \tiny   (≈ 5 pt)        | `<span style="font-size:0.5em">...</span>` |
| very small            | \scriptsize (≈ 7 pt)    | `<span style="font-size:0.7em">...</span>` |
| footnote-sized        | \footnotesize (≈ 8 pt)  | `<span style="font-size:0.8em">...</span>` |
| small                 | \small (≈ 9 pt)         | `<span style="font-size:0.9em">...</span>` |
| normal                | \normalsize (≈ 10 pt)   | `<span style="font-size:1em">...</span>  ` |
| big                   | \large (≈ 12 pt)        | `<span style="font-size:1.2em">...</span>` |
| very big              | \Large (≈ 14.4 pt)      | `<span style="font-size:1.4em">...</span>` |
| between big and huge  | \LARGE (≈ 17.3 pt)      | `<span style="font-size:1.7em">...</span>` |
| huge                  | \huge (≈ 20.7 pt)       | `<span style="font-size:2.1em">...</span>` |
| enormous, gigantic    | \Huge (≈ 24.9 pt)       | `<span style="font-size:2.5em">...</span>` |


```text
::: font large
This text is large.
:::
```

##### Center/Right alignment

```md
::: center
texte
:::

::: right
texte
:::
```

##### Alignment

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

### Complex Tables

Markdown offers limited table configuration—only column alignment by default. PyMdown provides captions, and superfences can inject more metadata, but we still miss:

- Table width (auto vs. full width)
- Resizing oversized tables
- Orientation (portrait vs. landscape)
- Column and row spanning
- Horizontal and vertical separator lines
- Column widths (fixed, auto, relative)

#### Extended Markdown Table Syntax

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

#### Cmi rules example

```latex
\begin{tabular}{@{}lll@{}}
\toprule
& \multicolumn{2}{c}{Reaction} \\
\cmidrule(l){2-3}
Person & Face & Exclamation \\
\midrule
\multirow[t]{2}{*}{VIPs} & :) & Nice \\
& :] & Sleek \\
Others & \multicolumn{2}{c}{Not available} \\
\bottomrule
\end{tabular}
```

#### Align to dot number

Find a syntax to align numbers to dot. `lS@{}`

#### Raw table syntax

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

### Arabic

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

### Figure References

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

## Issues

### Markdown Package Issues

`mkdocstrings` autorefs define heading anchors via `[](){#}`, which triggers Markdown lint violations. Find a syntax or lint configuration that avoids false positives.

### Syntax only ?

```latex
\usepackage{syntonly}
\syntaxonly
```
