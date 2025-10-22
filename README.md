# TeXSmith

TeXSmith is a Python package and CLI tool to convert **Markdown** or **HTML** documents into LaTeX format. It is designed to be extensible via templates and integrates with MkDocs for generating printable documents from documentation sites.

![TeXSmith Logo](docs/logo.svg)

## Features



## MkDocs plugin

L'objecif du projet est de pouvoir gérer la conversion LaTeX directement depuis MkDocs via un plugin. L'utilisation pourrait être la suivante:

```yaml
books: # On peut définir plusieurs documents de sortie pour une même documentation
 - template:
     root: Nom de la page utilisée comme base (on nav à partir de là)
     name: classic,vanilla,...
     language: fr # toujours présent, utile pour babel et autre. si ommi la langue de mkdocs est passée.
     attributes: # Défini par thème chaque thème à ses propre attributs.
       cover: circles # pousse dans le rendu de la template \VAR{cover} valant circles
       covercolor: indigo(dye)
       title: Titre du livre
       subtitle: Sous-titre
       author: Auteur
       frontmatter: # Utile pour la classe books qui fait cette distinction
        - Nom des pages qui doivent être dans le frontmatter
       backmatter:
        - Nom des pages qui doivent être dans le backmatter
       listoftables: true
       listoffigures: true
       index: true
       glossary: true
   debug:
    save_html: true # Save intermediate html in output folder
   copy_files: # Copy additional files to the output folder
    tex/*.sty: .
    docs/assets/logo.pdf: assets
   drop_title_index: true/false # dans le cas de Mkdocs, parfois l'index.md apparait comme lien sur
         une section du toc c'est une page courte mais pas un chapitre
   index_is_foreword: true # l'index peut être considéré comme un foreword avant le début d'un chapitre
```

## Render engine phases

The rendering pipeline walks the BeautifulSoup tree four times. Each pass maps
to a value of `RenderPhase` so handlers can opt into the point where their
transform should fire:

- **`RenderPhase.PRE`** – Early normalisation. Use it to clean the DOM and
  replace nodes before structural changes happen (e.g. unwrap unwanted tags,
  turn inline `<code>` into LaTeX).
- **`RenderPhase.BLOCK`** – Block-level transformations once the tree structure
  is stable. Typical consumers convert paragraphs, lists, or blockquotes into
  LaTeX environments.
- **`RenderPhase.INLINE`** – Inline formatting where block layout is already
  resolved. It is the right place for emphasis, inline math, or link handling.
- **`RenderPhase.POST`** – Final pass after children are processed. Use it for
  tasks that depend on previous passes such as heading numbering or emitting
  collected assets.

## MkDocs integration

Some features on printed documents are not handled by MkDocs or Python Markdown directly such as:

- [x] Index generation
- [x] Acronyms
- Glossaries
- Bibliography management

### Index generation

MkDocs generate a `search_index.json` consumed by lunr or wasabi to provide search capabilities in the generated HTML site. This index contains all words present in the documentation along with their locations. This is an automated way built dynamically on the browser side. However on LaTeX documents we need to generate a static index at compile time. In traditional LaTeX edition we use `\index{term}` commands scattered in the document, then we run `makeindex` or `xindy` to generate the index file included at the end of the document.

One strategy would be to implement a similar indexing pipeline that performs linguistic-driven keyword extraction from Markdown sources by combining structural and statistical cues. During parsing, code blocks are stripped, custom `{index,...}` annotations are honored, and each section is passed through spaCy (FR/EN) to extract noun-phrase candidates — sequences containing at least one **NOUN/PROPN** and no functional words. Terms are normalized, lemmatized, and filtered using multilingual stoplists plus an optional project stopfile. Statistical weighting integrates local context boosts (headings, captions, early position), lexical cohesion via a **PMI** heuristic for multi-word expressions, and logarithmic frequency scaling, with additional bias for forced terms. The resulting lexicon — a ranked JSON index — approximates a LaTeX-style `\index{…}` but is generated automatically from linguistic salience rather than manual markup.

In printed documents, index entries are often formatted typographically to indicate the relevance of a term in a given section:

- Normal text: the term is discussed in that section (default)
- Bold text: the term is the main topic of that section (topic)
- Italic text: the term is mentioned but not discussed (mentionned)
- Bold italic text: the term is both the main topic and mentioned elsewhere in the same section. (all)

This can be achieved in LaTex with `\index{term|textbf}`, `\index{term|textit}`, `\index{term|textbfit}` modifiers.

Either way a solution to manually add `\index{term}` in the LaTeX output or to generate automatically an index from the content is needed. We can combine this with tag generation for the search index in MkDocs. The chosen syntax could be:

```markdown
``{index,term1,term2,term3}
[](){index,term1,term2,term3}
[[term|index-term|b]], [[term|index-term|i]], [[term|index-term|bi]]
```

Either way this syntax should be ignored in the HTML output but processed in the LaTeX renderer to emit `\index{term1}`, `\index{term2|textbf}` etc. We can combine this into a mkdocs-plugin that generates index from this syntax and add tags in the search index for lunr/wasabi which can be cool. The renderer would detect this syntax and emit the corresponding LaTeX commands.

For this module as we parse HTML, we can define a new index handler on `<span data-index="term1" data-index-style="b">` or similar. It will be translatex into `\index{term1|textbf}` in LaTeX.

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

## Bibliography

This is a vast topic. In LaTeX we often use `biblatex` or `natbib` to manage bibliographies. The idea is to define references in a `.bib` file and cite them in the document with `\cite{key}` commands. The bibliography is then generated at the end of the document. Only the cited references are included.

Journals often have their own bibliography style to render references and display them in the bibliography section.

It is quite convenient when searching for an article to export the citation in BibTeX format and add it to the `.bib` file. However this format is not very human friendly and very verbose for simple references. Note that two versions exists: bibtex and biblatex which is an evolution of bibtex with more fields and better support for modern references (doi, url, etc.). For this project we will focus on biblatex format as it is more modern.

Python modules exists such as bibtexparser and pybtex but all of them are poorly coded (legacy Python, no type hints, no schema...). BibTeX is also quite old and not very well suited for modern references (DOI, URL, etc.). The original source code of Oren Patashnik (1988) can be used as base, also some documentation [Alexandre Feder](http://www.bibtex.org/Format/) contains a good overview of the format.

The CSL format (Citation Style Language) is a more modern approach to manage bibliographies. It is XML based and used by Zotero, Mendeley, etc. However it is more complex to parse and manipulate. The idea is to find a way to convert vintage `.bib` or `.biblatex` or `.bbl` files to a fully fledged format. Fuck this should be easier...

Citations styles is another topic. For LaTeX, the template will manage the format and the style so we don't care in TeXSmith. Some template may offer to customize through a configuration option, but this is not our concern. On the MkDocs case, the future plugin would be able to specify the format of the bibliography, and the sort order (nty, nyt, anyvt...) In traditional LaTeX the most common used formats are: abbrv, acm, alpha, apalike, ieeetr, plain, siam, unsrt.

Well what we want to achieve:

1. Accept to use `.bib` files and other common formats in the project and parse them to extract references. Bibtexparser can be used for that, but the project is not very well developped: no v2 on pypi, no schema, API not very clean. We will rewrite this.
2. Use doi2bib or similar services to fetch BibTeX entries from DOIs. DOIs are much easier to manage it is just a link such as `https://doi.org/10.1016/j.cub.2025.08.063`. The idea is to rely on several API services as fallback and implement a doi2bib function that fetches the BibTeX entry from a DOI.
3. Rely on a well defined schema (Pydantic) for biblatex entries to validate them and have a clean API to manipulate them.
4. Implement a two way conversion bib to python and python to bib.
5. Use common Markdown syntax to cite references. We can use footnotes syntax in an extended way `[^smith2020deep]`. I don't think this is conflicting with standard footnotes as the content is just a key. The renderer will detect this syntax and replace it with `\cite{smith2020deep}` in LaTeX.
6. If any citations is found we load any bibliography files passed to the renderer or on the CLI, parse them and collect the entries, we detect conflicts (same key different entry) and we generate the bibliography in the template  `\printbibliography`.
7. If a citation is not found in the bibliography, warn at build time.
8. Rely on a MkDocs plugin to manage bibliography on the project level and represent bibliography in the browser's documentation.

What I need before coding:

1. Find a Python package that can load, process a bib file. We will use pybtex.
2. Ensure the syntax `[^citekey]` works.

### Syntax

The `[^citekey]` syntax seems natural and well appropriated for citations in Markdown it is converted into `<sup id="fnref:citekey"><a class="footnote-ref" href="#fn:citekey">1</a></sup>` in HTML. The renderer can detect this pattern and replace it with `\cite{citekey}` in LaTeX. However if the footnote-ref is not defined in the document, the tag is not parsed and we get `[^chocolate]` in the HTML which could be fine as it is not conflicting (not in code sections). Footnotes are treated by the `footnotes` extension defined in Python Markdown and the code shows that.

### MkDocs

I found few plugins. The most cited is mkdocs-bibtex which is no longer maintained. mdx_bib is a Markdown extension that use the `@<citekey>` syntax why not, but it is not a standard Markdown syntax. We could support both `[^citekey]` and `@citekey` syntaxes. The plugin should also manage bibliography files at the project level.

So I think I will have to define my own... Piece of cake.

### Bibtex structure

```yml
type:
    article:
      required: [author, title, journal, year]
      optional: [volume, number, pages, month, note, doi, url, iss]
    book:
      required: [author|editor, title, publisher, year]
      optional: [volume|number, series, address, edition, month, note, doi, url, isbn]
    booklet:
        required: [title]
        optional: [author, howpublished, address, month, year, note, doi, url]
    conference:
        required: [author, title, booktitle, year]
        optional: [editor, volume|number, series, pages, address, month, organization, publisher, note, doi, url]
    inbook:
        required: [author|editor, title, chapter|pages, publisher, year]
        optional: [volume|number, series, type, address, edition, month, note, doi, url, isbn]
    incollection:
        required: [author, title, booktitle, publisher, year]
        optional: [editor, volume|number, series, type, chapter, pages, address, edition, month, note, doi, url, isbn]
    inproceedings:
        required: [author, title, booktitle, year]
        optional: [editor, volume|number, series, pages, address, month, organization, publisher, note, doi, url]
    manual:
        required: [title]
        optional: [author, organization, address, edition, month, year, note, doi, url]
    masterthesis:
        required: [author, title, school, year]
        optional: [type, address, month, note, doi, url]
    misc:
        required: []
        optional: [author, title, howpublished, month, year, note, doi, url]
    phdthesis:
        required: [author, title, school, year]
        optional: [type, address, month, note, doi, url]
    proceedings:
        required: [title, year]
        optional: [editor, volume|number, series, address, month, organization, publisher, note, doi, url]
    techreport:
        required: [author, title, institution, year]
        optional: [type, number, address, month, note, doi, url]
    unpublished:
        required: [author, title, note]
        optional: [month, year, doi, url]


citekey: |
    Unique identifier in the form m/\b[a-zA-Z0-9_-]+\b/. A standard pattern is
    authorYYYYTitleWord e.g. smith2020deep for an article by Smith in 2020 titled "Deep Learning for Cheese Analysis".
fields:
  address: Publisher address or the institution location.
  annote: An annotation
  author:
    description: List of authors in the form "First Last and First Last and ...
    type: list[str]
    remarks: in bibtex the "and" separator is used to separate authors.
  booktitle: Title of the book, conference proceedings, or collection.
  chapter: Chapter number
  edition: Edition of the book (e.g. "2nd").
  editor: List of editors in the form "First Last and First Last and ..."
  howpublished: How it was published (for misc type).
  institution: Institution name (for techreport type).
  journal: Journal name (for article type).
  month:
    description: Month of publication (e.g. "jan", "feb", etc.).
    type: int
    constraints: month >= 1 and month <= 12
    remarks: In bibtex months are represented as three-letter abbreviations.
  note: Additional notes.
  number: Issue number (for articles) or report number (for techreports).
  organization: Organization name (for conference type).
  pages: Page range (e.g. "12-34").
  publisher: Publisher name (for books).
  school: School name (for theses).
  series: Series name (for books that are part of a series).
  title: Title of the work.
  type: Type of report (for techreport type).
  volume: Volume number (for journals or books in a series).
  year:
    description: "Year of publication (e.g. "2020")."
    type: int
    constraints: year > 0 and year <= current_year
non-standard-fields:
  doi: Digital Object Identifier (e.g. "10.1016/j.cub.2025.08.063").
  url: URL to the online version of the work.
  issn: International Standard Serial Number (for journals).
  isbn: International Standard Book Number (for books).
```

## Figure caption

Pour cela il faut aller voir du côté de MkDocs et de Pandoc. En MkDocs les modules sont:

- mkdocs-caption
- mkdocs-img2fig
- mkdocs-img2figv2

## PyMdown caption

The good:


- Position top or bottom
- Rich text
- Use figcaption
- Auto numbering

The bad:

- Cumbersome syntax sensitive to indentation

```
Fruit      | Amount
---------- | ------
Apple      | 20
Peach      | 10
Banana     | 3
Watermelon | 1

/// caption
Fruit Count
///


![Image](image.png)

/// figure-caption
    attrs: {id: static-id}
Légende de l'image
///
```

## Mkdocs-caption

The good:

- Simple syntax
- Position top or bottom
- Refernce text

The bad:

- Index, numbering directly hardcoded
- No numbering relative to sections (unnumbered section in md)
- Figures number restart to 1 on each page
- No style management (caption cannot be bold, italic...)

```markdown
![This is the caption](image.png)

See how easy [](#_figure-1 is defined)

Table: table caption

| heading 1| heading 2 |
| - | - |
| content 1 | content 2 |
| content 3 | content 4 |

```
Avec Pandoc on peut faire:

```markdown
![This is the caption](image.png){#fig:label}
```

## TO-DO

### Priority

- [x] Remplacer safe_quote par requote_url de requests.utils
- [x] Remplacer fonctions helpers par package latexcodec
- [x] Remplacer to_kebab_case par python-slugify
- [x] Documenter class RenderPhase(Enum): chaque état et pourquoi.
- [x] Supporter la langue (babel) selon la configuration (polyglossia à venir)
- [x] Permettre l'écritre d'extensions Renderer,formatter (demo counter)
- [x] Support for index generation (makeindex, xindy)
- [x] Rename package texsmith et les templates texsmith-template-*
- [x] Activer toutes les extensions communes par défaut.
- [x] Support for bibliography (biblatex, natbib...)
- [x] Support for footnotes
- [x] Convert some journals templates
- [x] Ajouter des tests unitaires et d'intégration pour le CLI et MkDocs
- [x] Support for images (convertion to pdf...)
- [x] Manage figures captions
- [x] Manage table captions
- [ ] Verbose in CLI more details.
- [ ] Manage the figure (c.f.) how to manage that...
- [ ] Entrypoints (abstract, mainmatter, appendix...)
- [ ] Raw latex blocks (```latex { .texsmith } ... ```)
- [ ] Table width (auto width, fixed width..., tabularx, tabulary or not)

### Medium term

texsmith templates list # liste les templates installées (discover local et pip)
texsmith templates info book # affiche les infos sur la template book
texsmith templates scaffold my-template # crée un dossier my-template avec cookiecutter
- [ ] Documenter que par défaut, le renderer rends les blocs de code avec un wrapper générique, permettant de bind sur listing, verbatim ou minted.
- [ ] Gérer les assets de manière centralisée (images, drawio, mermaid...)
- [ ] Documenter le processus de création de templates LaTeX personnalisées
- [ ] Declare solution/exercises in a plugin way
- [ ] Find a way to have a solid and robust docker submodule/class

- [ ] Support for glossaries (glossaries package)
- [ ] Support for cross-references (cleveref package)
- [ ] Méthode pour extraire/injecter une section et ses sous-sections dans un autre entrypoint (frontmatter, abstract, appendix...)
- [ ] Add more Markdown extensions (definition lists, tables...)
- [ ] Improve error handling and reporting during LaTeX compilation
- [ ] Optimize asset conversion and caching mechanisms
- [ ] Mkdocs Integration
  - [ ] Support extensions in other MkDocs plugin (add latex syntax, transformers...)
- images (svg, png, webp, jpg...)
- drawio (.drawio, .dio)
- mermaid (.mmd, .mermaid, https://mermaid.live/edit#pako:eNpVjbFugz...)
- GraphViz (.graphviz, .dot)
- Plantuml (.plantuml, .puml
## Entry point

```md
---
meta:
  title: Mechanical Stiffness and Malleability of Hard Cheese
  subtitle: >
    A Rheological Study on the Viscoelastic Properties of Aged Cheese Varieties
  authors:
    - name: Dr. Jane Q. Dairy
      affiliation: Department of Food Mechanics, University of Edam, Netherlands
    - name: Dr. John P. Curds
      affiliation: Institute of Rheological Science, Swiss Cheese Laboratory
  date: Octobrer 20, 2025
  entrypoints:
    - title: Abstract
      target: abstract
    - title: Introduction
      target: mainmatter
---
## Abstract

The mechanical behavior of hard cheese varieties is a critical factor determining their processing, texture, and consumer perception.

## Introduction

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
```

Depuis la ligne de commande si on a plusieurs fichiers on peut spécifier l'entrypoint à utiliser:

```bash
texsmith convert
    -e abstract abstract.md
    -e mainmatter document.md
    -e appendix appendix.md
    -o output/
```
