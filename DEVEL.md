# Devel Notes

## TO-DO

### TeXSmith Core

The conversion engine, context models, templates, and bibliography tools now live in
the `texsmith.core` package. Legacy imports still point there, but new work should
reference the canonical module to avoid extra indirection.

- [x] Extract template aggregation into TemplateRenderer and slim TemplateSession
- [x] Remplacer safe_quote par requote_url de requests.utils
- [x] Remplacer fonctions helpers par package latexcodec
- [x] Remplacer to_kebab_case par python-slugify
- [x] Documenter class RenderPhase(Enum): chaque état et pourquoi.
- [x] Supporter la langue (babel) selon la configuration (polyglossia à venir)
- [x] Permettre l'écritre d'extensions Renderer,formatter (demo counter)
- [x] Support for index generation (makeindex, xindy)
- [x] Rename package texsmith et les templates texsmith-template-\*
- [x] Activer toutes les extensions communes par défaut.
- [x] Support for bibliography (biblatex, natbib...)
- [x] Support for footnotes
- [x] Convert some journals templates
- [x] Ajouter des tests unitaires et d'intégration pour le CLI et MkDocs
- [x] Support for images (convertion to pdf...)
- [x] Manage figures captions
- [x] Manage table captions
- [x] Slots can be defined in the frontmatter.
- [x] Find a way to have a solid and robust docker submodule/class
- [x] Declare solution/exercises in a plugin way
- [x] Add more Markdown extensions (definition lists, tables...)
- [x] drawio (.drawio, .dio)
- [x] mermaid (inline)
- [x] .mmd, .mermaid, `https://mermaid.live/edit#pako:eNpVjbFugz`...
- [x] Fonctionnement des emojis twemoji
- [x] Images marchent avec (.tiff, .webp, .avif, .gif, .png, .bmp...)
- [x] Verbose in CLI more details et afficher joliment les warnings et erreurs
- [x] --debug pour afficher les exceptions complètes
- [x] Bibliographie sur doi dans frontmatter
- [x] Perf increase by converting html to xml and use lxml not htmlparser?
- [x] Support multipages, je donnes plusieurs md ou html en entrée.
- [x] Improve error handling and reporting during LaTeX compilation
- [x] Raw latex input blocks (not visible in html)
- [x] Créer CI/CD
- [x] texsmith template info book
- [x] Raw latex blocks
- [x] Manage the figure (c.f.) how to manage that...
- [x] Optimize bibliography management using bib instead of jinja
- [x] Documenter le processus de création de templates LaTeX personnalisées
- [x] Support for hashtag index through the built-in `texsmith.index` extension
- [x] Textsc in Markdown
- [x] Noto Color Emoji ou {\fontspec{Symbola}\char"1F343} couleur ou nb
- [x] Make all examples build
- [x] Écrire documentation
- [x] Generating assets as sha only when using mkdocs, not texsmith directly or only when a specific option is enabled.
- [x] Fix or test __text__ in admonition.
- [ ] Do not require --shell-escape if minted is not used (no code or inline)
- [ ] Update dynamically in the latexmkrc the used engine (pdflatex, xelatex, lualatex)
- [ ] Base letter template on koma scrlttr2 adjust country-specific settings
- [ ] Add article template as "default" template part of TeXSmith
- [ ] Support for glossaries (glossaries package)
- [ ] Support for cross-references (cleveref package)
- [ ] Listings, verbatim ou minted
- [ ] Table width (auto width, fixed width..., tabularx, tabulary or not)
- [ ] Table orientation (large table landscape...)
- [ ] Scaffolding de templates avec cookiecutter
- [ ] texsmith template create my-template
- [ ] Index generation
- [ ] Progressbar support
- [ ] Compilation avec Docker ou TeXlive (choix)
- [ ] Documentation complete de docstring dans le projet
- [ ] Déployer sur PyPI

## Nox

We want the pyproject.toml support nox to test with all compatibles version 3.10, 3.11, 3.12, 3.13

## Index documentation.

In docs/guide/tags.md, Explain that MkDocs generate a `search_index.json` consumed by lunr or wasabi to provide search capabilities in the generated HTML site. This index contains all words present in the documentation along with their locations. This is an automated way built dynamically on the browser side. However on LaTeX documents we need to generate a static index at compile time. In traditional LaTeX edition we use `\index{term}` commands scattered in the document, then we run `makeindex` or `xindy` to generate the index file included at the end of the document.

In printed documents, index entries are often formatted typographically to indicate the relevance of a term in a given section:

- Normal text: the term is discussed in that section (default)
- Bold text: the term is the main topic of that section (topic)
- Italic text: the term is mentioned but not discussed (mentionned)
- Bold italic text: the term is both the main topic and mentioned elsewhere in the same section. (all)

TeXSmith unlocks through `texsmith.index` the syntax :

```markdown
{index}[a] One level index entry in default index
{index}[a][b][c](registry) Three levels nesting in the registry index
{index}[*a*] Formatted index entry in default index
{index}[**a**] Bold formatted index entry in default index
{index}[***a***] Bold italic formatted index entry in default index
{index}[a] {index}[b] Multiple index entries in one place
```

From an HTML perspective, we can define we can define a new index handler on `<span data-index="term1" data-index-style="b">`. It will be translatex into `\index{term1|textbf}` in LaTeX. MkDocs plugin, will parse the HTML and extract index to feed the Lunr index.

Eventually go to the files in docs/ to make sure we only reference to the new syntax everywhere.

### Glossary

I found a MkDocs glossary plugin: [ezglossary](https://realtimeprojects.github.io/mkdocs-ezglossary) but the syntax is weird. Why the semicolon, how to manage spaced entries or formatted ones? Would be nice to have several way to see it in browser : popup, tooltip, link to definition...

Moreover in LaTeX documents glossaries are often managed with the `glossaries` package which requires to define entries in the preamble with `\newglossaryentry`:

```latex
\newglossaryentry{clé}{
  name={forme singulière},
  plural={forme plurielle},
  description={texte descriptif},
  first={forme spéciale pour la première utilisation},
  text={forme normale (si tu veux la forcer)},
}
```

We can use `\gls` to use the standard form, `\Gls` to capitalize the first letter, `\glspl` for plural, `\Glspl` for capitalized plural. The first time the term is used it will use the `first` form if defined, otherwise the `name`. The description will be used in the glossary list. With markdown this is not possible. However, we can imagine a syntax to define glossary entries in markdown frontmatter:

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

Then we need an anchor base on the content where the term is defined:

```markdown
The **HTML**{#gls-html} is the standard markup language for web pages...
```

### Acronyms

\newglossaryentry{latex}
\newacronym

Glossaire :

Terme et définition

Accronym : en html c'est plutôt abbr qui est utilisé

C'est utilisé pour toujours utiliser l'accronyme sauf la première fois ou la valeur complète est utlisée sauf si on veut absolument la version short:

```tex
\gls nominal full première fois sinon courte
\Gls avec capitale
\acrshort uniquement court
\acrlong uniquement long
\acrfull version complète: Version Longue (VL)
```

Pour les entrées de glossaire:

```tex
\gls affiche le terme nominal
\Gls terme avec première lettre majuscule
\glspl le pluriel du terme
\Glspl plusiel avec première en majuscule


\newglossaryentry{clé}{
  name={forme singulière},
  plural={forme plurielle},
  description={texte descriptif},
  first={forme spéciale pour la première utilisation},
  text={forme normale (si tu veux la forcer)},
}

\newacronym{gcd}{GCD}{greatest common divisor}
```

-----

On veut gérer les abbréviations, s'il y a déjà quelque chose d'implémenté dans le code on refactor de la manière suivante.

En HTML une abbréviation est traduit par `<abbr title="description">term</abbr>`

On implémente le support avec:

1. Capture toutes les entrées abbr du document
2. Vérifie qu'il n'y a pas d'incohérence (même terme avec différente description) sinon on warn
3. On traduit en LaTeX par \acrshort{term}
4. On populate dans la template les acronyms via un attribut { 'key': ('term', 'description'), ... }
5. Le jinja de la template si acronyms n'est pas vide boucle pour créer les entrées d'acronymes via \newacronym{key}{term}{description}
6. On inclu dans les template conditionnellement : \usepackage[acronym]{glossaries} et \makeglossaries

-----

1. On veut renommer le package `texsmith` ainsi que l'exécutable. Renomme tout ce qu'il faut y compris les entrées de pyproject
2. On veut également renommer toutes les templates déclarées en texsmith-template-*
3. On veut déplacer les template dans un dossier templates

-----

Certaines templates commencent à part d'autres à chapter d'autres à sectin. Il faut indiquer dans toutes les templates le base_level de manière à ce qu'un `# foo` soit `part`, `chapter` ou `section` selon la template (documentclass). Ceci permet d'omettre de fixer le niveau à chaque appel en cli. On garde néanmoins la possibilité de faire un offset sur le document par exemple si on veut pas de part ou de chapter on peut shift de 2.

## Complex Tables

Tables, tables you are evil... In Markdown there not much room for configuring the tables. Only column alignment is supported. With PyMdown we can do captions, and with super fences we can imagine more properties.

What is truly missing?

- Table width
  - Auto (width according to content)
  - Full width (table take the full width of the page)
- Resize if too large: boolean
- Orientation: portrait/landscape
- Column/Row spanning
- Add separator lines (horizontal/vertical)
- Columns width (fixed, auto, relative...)

Superfences doesn't work with tables. We can define a new fence type `table` that would accept options in YAML format:

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
  - [Cell 4, null , Cell 6]
  - [Cell 7, Cell 8, null]
```
````

## Figures references

In LaTeX or any printed document, references depend on the language. In English we will say: "The elephant shown in Figure 1 is large.". To implement that in latex we do `The elephant shown in Figure~\ref{fig:elephant} is large.`. In Markdown with Pymdown we can do:

```markdown
The elephant shown in figure [#fig:elephant] is large.
```

```latex
\hyperref[fig:elephant]{Figure~\ref*{fig:elephant}}

\usepackage[nameinlink]{cleveref}
The elephant shown in \Cref{fig:elephant} is large.
L'éléphant montré en \cref{fig:elephant} est grand.
```

In scientific english we put "Figure" with a capital, but in french it is "figure" with a lowercase.

## Svgbob

[Svgbob](https://github.com/ivanceras/svgbob) lets you sketch diagrams using
ASCII art. Save the source with a `.bob` extension (or keep it inline) and link
to it like any other image:

```markdown
![Sequence diagram](assets/pipeline.bob)
```

During the build TeXSmith calls the bundled Svgbob converter, generates a PDF,
and inserts it in the final LaTeX output. Cached artefacts prevent repeated
rendering when the source diagram does not change.

## CircuitTikZ

[CircuitTikZ designer](https://circuit2tikz.tf.fau.de/designer/) is a handy way
to produce circuit diagrams from a browser. Export the generated TikZ snippet
and wrap it in a raw LaTeX fence:

```markdown
/// latex
\begin{circuitikz}
    \draw (0,0) to[battery] (0,2)
          -- (3,2) to[R=R] (3,0) -- (0,0);
\end{circuitikz}
///
```

The raw block bypasses the HTML output but is preserved in the LaTeX build. If
you prefer to keep the file separate, include it via `\input{}` in a raw fence
and store the `.tex` asset alongside your Markdown.

---

Verify that TeXSmith respects the following module design principles:

- Modules can inject, extend, and re-define functionality
- Modules are deterministic through topological ordering
- Modules foster reusability, with the possibility to remix them
- Modules can cooperate through well-defined contracts

----

Goal is to automatically convert Markdown table into latex tables with automatic break.

- Table allow break inside column in tables when table too wide.

----

Integrate book template into mkdocs:
- Remove HEIG-VD reference
- Remove cover page not necessary
- Use classic admonitions
- Use noto for code
- Choose serif/noserif for the font
- Inherit code configuration from article reduce arc in code, reduce thickness of frame
- Use default mermaid config (no color) which is not the case with the template
- Do not use french style
- Build mkdocs using parts as level0
- Do not show list of table if no tables
----

Reduce line height for code when have Unicode boxchars.

----

Style for inserted text ugly (green very round, see Formatting inserted text.

----

{~~deleted text~~} not rendered properly, curly brace kept.
----

TeXSmith mkdocs do not resolve hyperlinks in other pages for instance the :

[High-Level Workflows](api/high-level.md)

Is resolved as : the \ref{snippet:... is not defined anywhere.

For a deeper dive, start with High-Level Workflows \ref{snippet:1e3d017478b3bcb5fa151c3d783935d265bf00e8ba4066b23115acad60dc817b} and move

Fixed with \ref instead of something else. Build but don't work.
----

Issue with scientific paper cheese. code closed to early after snippet.

----

Base64 images md

![Hello World](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEYAAAAUCAAAAAAVAxSkAAABrUlEQVQ4y+3TPUvDQBgH8OdDOGa+oUMgk2MpdHIIgpSUiqC0OKirgxYX8QVFRQRpBRF8KShqLbgIYkUEteCgFVuqUEVxEIkvJFhae3m8S2KbSkcFBw9yHP88+eXucgH8kQZ/jSm4VDaIy9RKCpKac9NKgU4uEJNwhHhK3qvPBVO8rxRWmFXPF+NSM1KVMbwriAMwhDgVcrxeMZm85GR0PhvGJAAmyozJsbsxgNEir4iEjIK0SYqGd8sOR3rJAGN2BCEkOxhxMhpd8Mk0CXtZacxi1hr20mI/rzgnxayoidevcGuHXTC/q6QuYSMt1jC+gBIiMg12v2vb5NlklChiWnhmFZpwvxDGzuUzV8kOg+N8UUvNBp64vy9q3UN7gDXhwWLY2nMC3zRDibfsY7wjEkY79CdMZhrxSqqzxf4ZRPXwzWJirMicDa5KwiPeARygHXKNMQHEy3rMopDR20XNZGbJzUtrwDC/KshlLDWyqdmhxZzCsdYmf2fWZPoxCEDyfIvdtNQH0PRkH6Q51g8rFO3Qzxh2LbItcDCOpmuOsV7ntNaERe3v/lP/zO8yn4N+yNPrekmPAAAAAElFTkSuQmCC)

But not necessary optimal in term of sile size a 250kB image is about 5000 lines of base64.
----

## Markdown packages issues...

Mkdocs autorefs (from mkdocsstrings) definition `[](){#}` before heading gives Markdown lint issues.

## Lint/Format

Find a solution, none of the existing tools work well with mkdocs syntax.
