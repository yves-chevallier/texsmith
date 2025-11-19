# Devel Notes

Roadmap and development notes for TeXSmith. I maintain this file as a
checklist of features to implement, refactorings to perform, and documentation
to write this file will live within TeXSmith until version 1.0.0 is released.

## Roadmap

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
- [x] Base letter template on koma scrlttr2 adjust country-specific settings
- [x] Add article template as "default" template part of TeXSmith
- [x] Index generation
- [x] Progressbar support
- [ ] Integrate coverage
- [ ] Do not require --shell-escape if minted is not used (no code or inline)
- [ ] Update dynamically in the latexmkrc the used engine (pdflatex, xelatex, lualatex)
- [ ] Support for glossaries (glossaries package)
- [ ] Support for cross-references (cleveref package)
- [ ] Listings, verbatim ou minted
- [ ] Table width (auto width, fixed width..., tabularx, tabulary or not)
- [ ] Table orientation (large table landscape...)
- [ ] Scaffolding de templates avec cookiecutter
- [ ] texsmith template create my-template
- [ ] Compilation avec Docker ou TeXlive (choix)
- [ ] Integrate nox
- [ ] Documentation complete de docstring dans le projet
- [ ] Déployer sur PyPI

## We want to simplify the use of texsmith in CLI

Most of texsmith is used through the render command which can become the default.

We integrates the subcommands as dash options.

--list-extensions: shows all enabled extensions by default
--list-templates: shows all available templates specify builtin or third party or local templates found
--list-bibliography: shows when bibliography elements are found in the document or linked files. List pretty in a table like before
--template-info: shows information about the template used
--template-scaffold: create in the mentionned output folder a copy of the template specified with --template, easy to override or create new templates

Then we drop all commands mechanism, that simplify CLI usage. To build a document we could therefore do: texsmith foo.md --build (which will use the default template article if not specified.

Eventually update all the documentation to reflect that.

## Add in the documentation the usecase of texsmith to complete:

- Write a scientific article
- Write product documentation
- Write a book
- Write a letter
- Write cooking recipes
- Write technical reports

Huge advantage with conjunction with MkDocs is to have a single source of truth for both web and pdf output.
This enrich collaboration as all documentation is stored in markdown on git repository. Versnioning with Miked is easy and natural.

## .texsmith/config.toml

Improve documentation and structure of the user's configuration of texsmith. Goal is to be able to select default templates, mermaid style,
prefered options paper format for daily use of texsmith. This file is perfectly optional. TeXSmith can live anythwere from local folder or parent folders.
An existing folder .texsmith will be use by texsmith to store cache, config and other user specific data.

## Good integration of latexmkrc

We want always to generate a latexmkrc for all templates that simlpify the build.
To build we simply do latexmk and it build the correct file with the correct engine
and enable shell-escape if needed (if minted is used). We do not need to include minted logic and code features we no code blocks are used.

Can you check that and implement that?

## Nox

We want the pyproject.toml support nox to test with all compatibles version 3.10, 3.11, 3.12, 3.13

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

## Markdown packages issues

Mkdocs autorefs (from mkdocsstrings) definition `[](){#}` before heading gives Markdown lint issues.

## Lint/Format

Find a solution, none of the existing tools work well with mkdocs syntax.
