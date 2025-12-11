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
- [x] Configure style for code highlight pygments default is bw
- [x] Snippet template
- [x] Drawio Exporter remote via wreight... see in scripts
- [x] Mermaid color configuration for MkDocs
- [x] Build MkDocs with parts at level 0.
- [x] Implement drawio over pywreight
- [x] Font style with mono
- [x] MkDocs Linking Issues
- [x] Clean book template
- [x] Hide the list of tables when no tables exist.
- [x] Manage title fragment to insert title meta
- [x] Manage fragments order from before/after hooks instead of in fragments.py
- [ ] Complete docstrings in the codebase for better mkdocstrings generation
- [ ] Refactoring snippets and fix snippet templates
- [ ] Mono fallback fonts
- [ ] Solve issue with Greek fonts
- [ ] Utiliser \caps de soul au lieu de textsc pour le smallcaps
- [ ] Be verbose in mkdocs show what happens (fetching assets, building...)
- [ ] Global user's configuration (.texsmith/config.yml)
- [ ] os: [ubuntu-latest, windows-latest, macos-latest]
- [ ] Unified Fences Syntax
  - [ ] Multicolumns
  - [ ] Font Size
  - [ ] Center/Right alignment
  - [ ] Language
  - [ ] LaTeX only / HTML only
  - [ ] LaTeX raw
- [ ] Add example: university exam
- [ ] Acronyms multiline
- [ ] Support for {++inserted text++}, and {~~deleted text~~} (goodbox)
- [ ] docs/syntax/captions.md (captions not working when using texsmith?)
- [ ] Make CI pass
- [ ] Support for multi-indexes (dates, ...)
- [ ] Support cross-references (cleveref package)
- [ ] Add table width controls (auto, fixed width, `tabularx`, `tabulary`, etc.)
- [ ] Support table orientation (rotate very wide tables)
- [ ] Scaffold templates with Cookiecutter
- [ ] Implement `texsmith template create my-template`
- [ ] Deploy to PyPI
- [ ] CI: uv run mkdocs build #--strict not yet ready
- [ ] Windows Support
- [ ] Insert Examples PDFs in the GitHub Releases
- [ ] Ts-Extra
  - [ ] tocloft
  - [ ] enumitem
- [ ] Develop submodules as standalone plugins
  - [ ] Marginalia (`marginpar` package with footnotes syntax)
  - [ ] Epigraph Plugin
  - [ ] Letterine
  - [ ] Custom variables to insert in a document using moustaches
- [ ] Simplify the attributes SSOT for templates and fragments
- [ ] ts-languages that uses polyglossia and specific things to languages
- [ ] Analyse which license suit best TeXSmith
- [ ] Update docs/api to reflect the actual codebase
- [ ] Add comprehensive docstring in each docs/api entrypoint in the codebase to explain why/the architecture and how it is useful.
- [ ] Do not show temporary paths in outputs CLI summary table (│ Main document │ /tmp/texsmith-x84gefq4/colorful.tex │)

## Directives

- DO NOT keep any backward compatibility for now. We are still in pre-1.0.0 phase.
- DO NOT introduce any shim or compatibility layer. Everything must be clean and simple.
- The unit tests can be changed at will to reflect the new codebase this is not a contract yet.
- The **PRIMARY GOAL** is to have a clean, simple, maintainable, documented codebase with clear separation of responsabilities, simplify at best.
- Finish all plan with a cleaning pass to remove any dead code, and all old API that is not used anymore.
- Write docstrings for everything.
- Always finish with uv run ruff check . and uv run ruff format .

## Fonts

We want to refactor and rework the fonts mechanism it is too clumpsy complex and vague. The texsmith/fonts folder contains 14 files plus data files which is too much.
The goal is to have a clear separation of responsabilities and a clear definition of what is TeXSmith Core API and what is ts-fonts fragment.

TeXSmith Core API is in charge of:

- detecting used codepoints in document/multidocument
- associate text regions to a language script and to a Noto Font
- download the requested Noto Fonts
- download the requested Emojis fonts

TeXSmith ts-fonts fragment is in charge of:

- Defining available fonts packages
- Building the ts-fonts to be engines friendly (xelatex, tectonic, lualatex...)
- Populate ucharclasses ranges based on usage (information got from TeXSmith Core)

## Predefined Fonts Package

The PROFILE_MAP in selection.py should not be defined here, but rather in the ts-fonts fragment which is responsible of loading fonts. Plus we have some SSOT for instance in _KPSE_FAMILIES in locator.py.

In order to simplify everything about font management in TeXSmith, we will only configure the standard fonts from ts-fonts fragment the same manner as fonts-test.tex demonstrates it in the root of the project. Of course we want a compatible version for xelatex and lualatex. To be compatible with tectonic we absolutly need the full font name not the description name used by harfbuzz.

Some of these fonts needs to be downloaded from CTAN (at least the .sty). The ts-fonts can be in charge of downloading these packages extract the zip and get the .sty files in the build folder, conditionnally if the font is used. We can keep a cache folder in ~/.texsmith/fonts/ for these downloaded packages.

By default we use `lm` as the default font package.

From now on TeXSmith only supports these packages which are available through tectonic or TeXLive automatically we **do not** need a mechanism to download or copy any of these fonts except the style files if needed.

## Font Copy

Previously, TeXSmith copied all fonts in the build fonts/ folder. For the standard documents described above, we do not need to copy all fonts anymore. Except for
fallbacks which is described below.

## Fallback

In LuaLaTeX on utilise quelque chose comme (regarde l'actuel ts-fonts):

```tex
\defaultfontfeatures{FallbackFamilies = {{Noto Emoji...}}} pour les fallback ou alors par cohérence avec XeLaTeX:

\defaultfontfeatures{
  Renderer=HarfBuzz,
  RawFeature = {
      fallback=range:1F300-1FAFF,Noto Emoji
  }
}
```

On XeLaTeX/Tectonic, we need to declare the fallback using ucharclasses like we actually do in ts-fonts.
As it is a fallback. We only include ranges that are not covered by the main fonts **THIS IS IMPORTANT**:

Emojis will naturally be in treated by these fallbacks. No need to add specific case for them.

We will recycle the old implementation and simplify it to have a precise mechanssm for fallback detection and match to fonts.

Noto is the default fallback font family for all scripts not covered by the main fonts. These fonts are downloaded on demand if required by the document
cached in ~/.texsmith/fonts/ and copied in the build folder if used and needed only.

## Emojis

Currently TeXSmith supports OpenMoji which is downloaded on demand if any emoji is used in the document. TeXSmith can rely on a "Font Fetcher" mechanism to download
a font that cover the requested codepoints. So this works for emojis. As Noto Color Emoji is not compatible with XeLaTeX due to the COLR/CPAL format, we will keep OpenMoji as the default emoji font for XeLaTeX and Tectonic for now.

## Redondance

attr_numbered = (
        _lookup_bool(attribute_overrides, ("numbered",))
        or _lookup_bool(attribute_overrides, ("press", "numbered"))
    )

## Tables

Long table et auto ajustement.

```latex
\documentclass{article}
\usepackage[margin=2cm]{geometry}
\usepackage{booktabs}
\usepackage[french]{babel}
\usepackage{array}

% ltablex : Le pont entre tabularx et longtable
\usepackage{ltablex}

% IMPORTANT : On NE met PAS \keepXColumns ici.
% Sans cette commande, ltablex va calculer si le tableau a besoin
% de toute la largeur ou non.

\begin{document}

\section*{Cas 1 : Table petite (Compacte)}
% Ici, comme le texte est court, le tableau ne prendra pas toute la page
% Les colonnes X vont se comporter comme des colonnes 'l'
\begin{tabularx}{\textwidth}{lXX}
    \toprule
    \textbf{ID} & \textbf{Statut} & \textbf{Note} \\
    \midrule
    \endfirsthead
    1 & OK & R.A.S. \\
    \midrule
\end{tabularx}

\vspace{2cm}

\section*{Cas 2 : Table large (Extension automatique)}
% Ici, le texte est long. Le tableau va détecter qu'il dépasse,
% s'étendre jusqu'à \textwidth, et activer le retour à la ligne.
\begin{tabularx}{\textwidth}{lXX}
    \toprule
    \textbf{ID} & \textbf{Description} & \textbf{Analyse} \\
    \midrule
    \endfirsthead

    \textbf{ID} & \textbf{Description} & \textbf{Analyse} \\
    \midrule
    \endhead

    204 &
    Ici j'ai un texte suffisamment long pour justifier que le tableau prenne toute la largeur disponible sur la page. &
    Et ici une autre colonne qui va se partager l'espace restant équitablement avec la colonne précédente. \\

    205 & Test de remplissage & Encore du texte... \\
    \bottomrule
\end{tabularx}
\end{document}
```

## PLAN

1. Load in your context how ts-fonts and TeXSmith use the fonts mechanisms lean the architecture
2. Establish a complete refactoring plan related to fonts management
3. Implement the plan step by step where the old codebase related to fonts is **FULLY** replaced by the new one.
4. Test to build with the examples (examples/make clean all)
5. Document in docs/guide/fonts.md the new mechanism, the compatible fonts packages etc.
6. Clean the codebase remove any dead code.

##

inline.py:

"""Advanced inline handlers ported from the legacy renderer."""


Use figure admonition

!!! figure

  ![Alt](image.png)

  Caption... you can explain whatever here

Multiple figures

!!! figure

  ![a](image.png)
  ![b](image.png)

  Caption... you can explain whatever here


Or table admonition

!!! table

Or mermaid diagram

!!! figure

    ```mermaid
    flowchart LR
        A --> B
        B --> C
    ```

    Example diagram caption


Configuration with:

.texsmith/

- Recursively search for .texsmith folder in your path
- All .texsmith configuration can be overritten

---

Captions

Captions in Markdown is a huge mess. Plenty of obsolete extensions attempted to provide a mechanism
to add rich captions for figure and tables and refer to them. PyMdown added in 10.12 the syntax:

```
/// caption
...
///
```

which can add captions to figures or tables, but discrimination of target (figure or table) is
not done automatically you must specify `figure-caption` or `table-caption`

The subfigures with the `| ^1` syntax works, but is not optimal for latex rendering and the reference id generated with `attrs: {id: static-id}` can be derouting.

TeXSmith offers a more convenient way of adding figures using the admonition style

!!! figure { #reference }

   ![alt](image.png)

   Caption...

You can automatically use subfigures with the following. The layout attribute will dictate how the figures are agenced in the output (`2:1` two figures horizontally, `2:2` four figures in two columns with two rows.

!!! figure { #reference layout="2:1" }

   ![a](image.png)
   ![b](image.png)

   We see in (a) a figure and in (b) another one.

To refer to figures, use the `[](reference)` which will be replaced by the element number.

```markdown
We see in Figure [](duck) that the animal has two legs.
```

## Tectonic log

We want to mute false warnings and not display them:

```perl
/^warning:\s*.*?:\d+:\s*Requested font.*?at.*$/
/^warning:\s*.*?:\d+:\s*Unknown feature.*?in font.*$/
```

Recent matrix runs with TeX Gyre (bonum/pagella/termes/schola/heros/adventor/cursor) trigger
many Tectonic warnings like `Unknown feature '` or repeated `Requested font` lines; output is
otherwise correct. Keep these noted as benign until we wire the log filter above or document a
flag to silence them.

## Snippets for on doc examples:

We currently use this syntax which is aweful with plenty of parameters. I want to provide an alternative syntax using code fences

Here the current syntax for two examples:

````md {.snippet data-caption="Download PDF" data-attr-format="din" data-drop-title="true" data-frame="true" data-width="80%" data-cwd="../../examples/letter/"}
---8<--- "examples/letter/letter.md"
````

````md {.snippet data-caption="Download PDF" data-frame="true" data-template="article" data-layout="2x2" data-width="70%" data-files="cheese.bib" data-cwd="../../examples/paper/"}
---8<--- "examples/paper/cheese.md"
````

Here the alternative syntax whcih doesn't use the ---8<--- mechanism:

```yaml { .snippet width=80% }
cwd: ../../examples/letter
sources:
  - letter.md
press:
  format: din
  frame: true
```

```yaml { .snippet width=70% }
layout: 2x2
cwd: ../../examples/paper
sources:
  - cheese.md
  - cheese.bib
press:
  frame: true
```

## Frame with dog-ear

TeXSmith have two different mechanism to add fancy frame around pages:

1. On preview PNG, by drawing manually the frame for having a good preview.
2. On LaTeX snippet template only.

## ts-frame

Implement a new fragment `ts-frame` which use the `frame` boolean attribute. If enabled we add a small frame on each page, the same way does the snippet template on the PDF. To be more functional we might automatically inject in latex  using a `\AddToHook{shipout/foreground}{%` for instance:

```latex
\usepackage{tikz}
\usetikzlibrary{calc,backgrounds}

\AddToHook{shipout/foreground}{%
  \begin{tikzpicture}[remember picture,overlay]
    \def\margin{1cm} % marge du cadre par rapport au bord de la page
    \def\e{1cm}      % taille du coin replié

    \coordinate (A) at ($(current page.north west) + (\margin,-\margin)$);
    \coordinate (B) at ($(current page.north east) + (-\margin,-\margin)$);
    \coordinate (C) at ($(current page.south east) + (-\margin,\margin)$);
    \coordinate (D) at ($(current page.south west) + (\margin,\margin)$);

    \coordinate (Bdown) at ($(B)-(0,\e)$);
    \coordinate (Bleft) at ($(B)-(\e,0)$);
    \coordinate (Corner) at ($(B)-(\e,\e)$);

    \draw (A) -- (Bleft) -- (Bdown) -- (C) -- (D) -- cycle;
    \draw (Corner)
     .. controls ($(Corner)+(0.3*\e,0.1*\e)$) and ($(Bdown)+(-0.3*\e,-0.1*\e)$) ..
     (Bdown);
    \draw (Bleft)
     .. controls ($(Bleft)+(0.1*\e,-0.3*\e)$) and ($(Corner)+(-0.1*\e,0.3*\e)$) ..
     (Corner);
  \end{tikzpicture}%
}
```

This mechanism only works on not standalone documents I think. So the fragment should be compatible with article, letter and book, not the snippet template which still use its own version. In this case the attribute is declared in the template snippet

Pour être cohérent on va utiliser les attributs suivants:

```yaml
frame: false (default, no frame added, nothing added in the tex output) | true (juste un cadre) | curl (active le coin replié)
```

## Makeindex with engine tectonic

With the engine `tectonic`, makeindex is not called automatically same for bibtex and makeglossaries. The goal is to implement that in TeXSmith. If the document uses an index, a glossary, or a bibliography, TeXSmith should call the appropriate tools between compilation passes.
And rerun the compilation until all references are resolved.

For the tools for index we look for `texindy` or `makeindex` in this order. The first one found is used.

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
