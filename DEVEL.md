
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

### Acronyms

\newglossaryentry{latex}
\newacronym

Glossaire :

Terme et définition

Accronym : en html c'est plutôt abbr qui est utilisé

C'est utilisé pour toujours utiliser l'accronyme sauf la première fois ou la valeur complète est utlisée sauf si on veut absolument la version short:

\gls nominal full première fois sinon courte
\Gls avec capitale
\acrshort uniquement court
\acrlong uniquement long
\acrfull version complète: Version Longue (VL)

Pour les entrées de glossaire:

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

---

1. On veut renommer le package `texsmith` ainsi que l'exécutable. Renomme tout ce qu'il faut y compris les entrées de pyproject
2. On veut également renommer toutes les templates déclarées en texsmith-template-*
3. On veut déplacer les template dans un dossier templates

---

Certaines templates commencent à part d'autres à chapter d'autres à sectin. Il faut indiquer dans toutes les templates le base_level de manière à ce qu'un `# foo` soit `part`, `chapter` ou `section` selon la template (documentclass). Ceci permet d'omettre de fixer le niveau à chaque appel en cli. On garde néanmoins la possibilité de faire un offset sur le document par exemple si on veut pas de part ou de chapter on peut shift de 2.

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
6. If any citations is found we load any bibliography files passed to the renderer or on the CLI, parse them and collect the entries, we detect conflicts (same key different entry) and we generate the bibliography in the template `\printbibliography`.
7. If a citation is not found in the bibliography, warn at build time.
8. Rely on a MkDocs plugin to manage bibliography on the project level and represent bibliography in the browser's documentation.

What I need before coding:

1. Find a Python package that can load, process a bib file. We will use pybtex.
2. Ensure the syntax `[^citekey]` works.


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

## TO-DO

### TeXSmith Core

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
- [x] .mmd, .mermaid, https://mermaid.live/edit#pako:eNpVjbFugz...
- [x] Fonctionnement des emojis twemoji
- [x] Images marchent avec (.tiff, .webp, .avif, .gif, .png, .bmp...)
- [x] Verbose in CLI more details et afficher joliment les warnings et erreurs
- [x] --debug pour afficher les exceptions complètes
- [ ] Bibliographie sur doi dans frontmatter
- [ ] Perf increase by converting html to xml and use lxml not htmlparser?
- [ ] Support multipages, je donnes plusieurs md ou html en entrée.
- [ ] Manage the figure (c.f.) how to manage that...
- [ ] Optimize bibliography management using bib instead of jinja
- [ ] Raw latex blocks (`latex { .texsmith } ... `)
- [ ] Table width (auto width, fixed width..., tabularx, tabulary or not)
- [ ] Table orientation (large table landscape...)
- [ ] Scaffolding de templates avec cookiecutter
- [ ] Documenter le processus de création de templates LaTeX personnalisées
- [ ] Improve error handling and reporting during LaTeX compilation
- [ ] Listings, verbatim ou minted
- [ ] Support for glossaries (glossaries package)
- [ ] Support for cross-references (cleveref package)
- [ ] texsmith template create my-template
- [ ] texsmith template info book
- [ ] Index generation
- [ ] Compilation avec Docker ou TeXlive (choix)
- [ ] Créer CI/CD
- [ ] Écrire documentation
- [ ] Documentation complete de docstring dans le projet
- [ ] Déployer sur PyPI

## MkDocs plugin

### Intégration

L'objectif est de créer un plugin MkDocs (`mkdocs-latex-plugin`) qui utilise TeXSmith pour générer le contenu LaTeX à partir du HTML généré par MkDocs.

Seulement si on fait un mkdocs build, a la fin du processus de build on aura dans site déjà toutes les images rendues et tous les html. On peut donc récupérer les fichiers, construire la navigation et passer tout ça à TeXSmith pour générer le pdf final. On crée dans un répertoire `press` qui contient les fichiers intermédiaires LaTeX et le pdf final, organisé par ouvrage.

On peut configuer le plugin pour gérer plusieurs pdf dans la même documentation avec des templates différentes, des parties différentes. Tout est configuré dans le mkdocs.yml.

Il faut supporter les truc spécifiques à MkDocs : tabbed, admonitions supplémentaires, glightbox.

### Configuration

L'objecif du projet est de pouvoir gérer la conversion LaTeX directement depuis MkDocs via un plugin. L'utilisation pourrait être la suivante:

```yaml
books: # On peut définir plusieurs documents de sortie pour une même documentation
 - main: Nom de la page utilisée comme base (on nav à partir de là)
     name: classic,vanilla,...
     language: fr # toujours présent, utile pour babel et autre. si ommi la langue de mkdocs est passée.
     attributes: # Défini par thème chaque thème à ses propre attributs.
       slots:
         abstract: abstract.md
         frontmatter: [frontmatter.md, Section Name]
       meta:
         title: Titre du livre
         subtitle: Sous-titre
         author: Auteur
         listoftables: true
         coverpage: true
   debug:
    save_html: true # Save intermediate html in output folder
   copy_files: # Copy additional files to the output folder
    tex/*.sty: .
    docs/assets/logo.pdf: assets
   drop_title_index: true/false # dans le cas de Mkdocs, parfois l'index.md apparait comme lien sur
         une section du toc c'est une page courte mais pas un chapitre
   index_is_foreword: true # l'index peut être considéré comme un foreword avant le début d'un chapitre
```

### MkDocs plugin TO-DO

- [ ] Support extensions in other MkDocs plugin

## Sandbox

Pour la template article on veut sortir callout dans un callout.sty et faire quelque chose de propre

Pareil pour la configuration de listing avec un code.sty qui importe le nécessaire et défini les commandes

On veut ces fichiers robustes

---

POur la bibliographie, pour l'instant dans la template article tu as ceci:

\begin{thebibliography}{\VAR{citations|length}}
\BLOCK{ for key in citations }
\BLOCK{ set entry = bibliography_entries.get(key) }
\bibitem{\VAR{key}}%
\BLOCK{ if entry }
\BLOCK{ set fields = entry['fields'] }
\BLOCK{ set persons = entry['persons'] }
\BLOCK{ set authors = persons.get('author', []) }
\BLOCK{ if authors }\VAR{ authors | map(attribute='text') | join(', ') }\BLOCK{ endif }%
\BLOCK{ if fields.get('title') } \textit{\VAR{fields['title']}}\BLOCK{ endif }%
\BLOCK{ if fields.get('journal') } \VAR{fields['journal']}\BLOCK{ endif }%
\BLOCK{ if fields.get('year') } (\VAR{fields['year']})\BLOCK{ endif }%
\BLOCK{ if fields.get('url') }\\\url{\VAR{fields['url']}}\BLOCK{ endif }%
\BLOCK{ if fields.get('doi') }\\\textsc{doi}: \VAR{fields['doi']|latex_escape}\BLOCK{ endif }
\BLOCK{ else }
Missing bibliography entry for \VAR{key}
\BLOCK{ endif }
\BLOCK{ endfor }
\end{thebibliography}

Mais on pourrait passer par biber pour mieux gérer ça et passer par le .bib non ?


---

# Gestion multidocument

L'objectif est de supporter la gestion multidocument c'est à dire que j'ai plusieurs fichiers que je donne dans le cli :

texsmith foo.md bar.md baz.md

Il crée une traduction de chaque élément foo.tex, bar.tex et baz.tex dans le répertoire de sortie
Si je donne une template -t book il va insérer dedans l'import de chacun de ces fichiers
\input{foo}
\input{bar}
\input{baz}

Bien entendu je peux spécifier le slot de destination pour chaque fichier ou élément:

texsmith *.md -s abstract:foo.md -s backmatter:bar.md:"section b"

Il faut décider d'une stratégie si on passe par un \input ou si on copy/pase le fichier dans la destination.

- S'il s'agit d'un fichier complet on utilise input
- S'il s'agit d'une extraction d'une section ou d'une partie on copy/paste

Autre point à considérer. Selon l'appel de texsmith:

$ texsmith convert foo.md # Sortie sur STDOUT
$ texsmith convert foo.md -o foo.tex # Sortie sur fichier
$ texsmith convert foo.md bar.md -o foobar.tex # Pas d'\input mais tout concaténé, dans l'ordre des fichiers
$ texsmith convert foo.md bar.md -t template # Répertoire par défaut `build` et \input utilisés
