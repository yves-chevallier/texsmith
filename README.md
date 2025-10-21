On va rajouter au cli texsmith :

-h,--heading-level permettant d'indenter tous les niveau (section -> subsection) si le document intervient dans un document plus général
-o,--output-dir répertoire de sortie ou sont également copiés les artefacts (téléchargement des images sur internet, conversion des svg, drawio, mermaid en pdf, toutes les images en png)
-a,--copy-assets Oui ou non copier et générer les assets (images, documents dans les hyperref)



Dans cette fonction il y a de la logique qu'on va toujours utiliser :

- être sensible à un tag
- requirement sur les classes
- process content
- gather attributes
- apply template with those attributes.

Le context.formatter.codeblock(
        code=code_text,
        language=language,
        lineno=lineno,
        filename=filename,
        highlight=highlight,
        baselinestretch=baselinestretch,
    ) me semble un peu superflu on passe certains attributs au formatter, il peut être sensible ou non à ces attributs, cela oblige  que le renderer ne soit défini.

Mettons que j'aimerais ajouter le support pour


Pour le moment on gère la logique d'application avec RenderPhase et priority mais

Il convient de définir les logiques d'application. Les tags:

del
mark
em
strong
sup
sub
ins

Peuvent apparaitre dans

p
h1,h2,h3,h4,h5
dl->dt, ul->li
details->p, details->summary

mais rien ne peut apparaitre dans:

code



Je pense qu'il serait bien de traiter les assets :
- images (svg, png, webp, jpg...)
- drawio (.drawio, .dio)
- mermaid (.mmd, .mermaid, https://mermaid.live/edit#pako:eNpVjbFugz...)
- GraphViz (.graphviz, .dot)
- Plantuml (.plantuml, .puml

De manière plus intelligente. En LaTeX tous ces assets seront converti en pdf inclus avec includegraphics, on retrouve donc pgcd.drawio dans un src par exemple qu'il faudra convertir en assets pgcd.drawio.pdf mais comme il peut y avoir un conflit de nom on sauve avec le hash assets/09a5ce2cd520c8895e8bd6b3d7e55596e570e075.pdf l'avantage est que si l'asset est généré on n'est pas obligé de le regénérer s'il existe déjà le hash va dépendre de la source. Si c'est un asset fixe on peut calculer le hash sur le nom et la taille du fichier mais si c'est un asset textuel (comme un svg, drawio, mmd... on peut calculer le hash sur le contenu.

En amont si on utilise mkdocs pour produire le html, il aura copié les assets dans le répertoire site/ et on y aura directement accès.

Je me dit qu'on pourrait centraliser la gestion des assets, générer un fichier de manifest avec la liste de tous les assets inclus (correspondance entre le nom du fichier (chemin relatif ou absolu ou url, le nom de l'asset compilée, le fichier dans lequel il apparait (path/file.tex).

Donc dans un renderer quand on récupère le nom d'un asset (qu'on peut identifier avec une fonction), on peut récupérer de manière centralisée dans le package son hash pour remplacer le lien, vérifier l'existence du fichier, faire la conversion...

Je ne sais pas comment c'est fait en ce moment mais peut-être qu'il y aurait moyen d'optimiser qu'en penses-tu ?

Dans le HTML généré


Extraction d'un url mermaid avec pako:

data = url.split("#pako:")[1]
decoded = base64.urlsafe_b64decode(data + "==")
mermaid_code = zlib.decompress(decoded).decode("utf-8")

on peut récupérer le code mermaid?


## Templates LaTeX

Le code LaTeX généré ne contient pas de balises `\begin{document}` ni de préambule `\documentclass{...}`. Cela permet d'insérer le contenu généré dans un document LaTeX plus large. Pour constuire un document complet, il est nécessaire de spécifier `--template` lors de l'appel à la commande `texsmith convert`.

Le templates sont des packets PIP nommés `texsmith-template-<nom>` ou des dossiers locaux contenant les fichiers nécessaires.

Une template contient:

- Des fichiers `.cls`, `.sty` ou `.tex` qui peuvent contenir la syntaxe Jinja2 (`\VAR{title}` ou `\BLOCK{if foo}\BLOCK{endif}`) pour insérer des variables dynamiques.
- Des assets additionnels (images, logos, polices...).
- Un fichier `manifest.toml` décrivant la template (nom, version, engine LaTeX, paquets tlmgr nécessaires, attributs de configuration...).
- Des overrides des partials Jinja2 utilisés pour générer certains éléments (codeblock, figure...).
- Un fichier `README.md` documentant la template.
- Un `__init__.py` déclarant la classe de template pour le plugin MkDocs.

La classe Template héritée de l'interface dans le package `latex` permet de:

- Rendre la template en recevant les attributs passés par l'utilisateur (titre, auteur, couverture...).
- Traiter les erreurs spécifiques à la template, mauvais attributs, valeurs invalides...
- Fournir le chemin vers les fichiers de la template et l'accès au manifest via un schéma Pydantic propre.
- Définir un Pre/Post hook pour copier les assets spécifiques à la template.
- Override certaine éléments du Formatter ou du Renderer si nécessaire (support de balises supplémentaire, traitement de cas particulier).

Gestion de la complate facile avec cookicutter pour créer une nouvelle template.
Structure rigide avec cookiecutter, manifest simple...

Au niveau du CLI on peut imaginer un :

```bash
texsmith templates list # liste les templates installées (discover local et pip)
texsmith templates info book # affiche les infos sur la template book
texsmith templates scaffold my-template # crée un dossier my-template avec cookiecutter
texsmith convert --template=./book/ # utilise la template locale book
```

Lorsqu'une template est sélectionnée avec `--template`, le fragment LaTeX produit par le renderer est inséré dans la clé `mainmatter` du template. Les autres attributs restent définis par défaut via le `manifest.toml`, garantissant un document complet sans modifier le contenu généré.

Le manifest peut également déclarer des entrées `[latex.template.assets.<destination>]` listant les fichiers ou dossiers à copier vers le dossier de sortie. Le CLI s'occupe de recopier ces ressources à l'endroit défini, ce qui garantit que les classes, couvertures et autres dépendances nécessaires à la compilation LaTeX soient disponibles. Lorsqu'un fichier doit être interprété par Jinja avant d'être déployé (par exemple `covers/circles.tex`), on peut ajouter `template = true` :

```toml
[latex.template.assets."covers/circles.tex"]
source = "covers/circles.tex"
template = true
```

Pour tester la template `book` incluse dans le dépôt :

```bash
uv run texsmith convert tests/test_mkdocs/docs/index.md --template=templates/texsmith-template-book/texsmith_template_book
```

Après installation du paquet dédié (`uv pip install -e templates/texsmith-template-book` ou `uv add texsmith-template-book`), la même template est disponible via son entrée `book` :

```bash
uv run texsmith convert tests/test_mkdocs/docs/index.md --template=book
```

Une variante minimale est disponible avec la template `article`, pensée pour des documents courts. Elle expose uniquement les attributs `title`, `author`, `date`, ainsi que `paper` (converti en option `a4paper`, `a3paper`, etc.) et `orientation` (`portrait` ou `landscape`) qui ajustent directement `\documentclass`.

```bash
uv run texsmith convert tests/test_mkdocs/docs/index.md --template=templates/texsmith-template-article/texsmith_template_article
uv run texsmith convert tests/test_mkdocs/docs/index.md --template=article
```

Lorsque `--template` est fourni, le convertisseur écrit automatiquement le résultat LaTeX complet dans le répertoire passé via `--output-dir` (par défaut `build/`) en utilisant le nom du fichier source avec l’extension `.tex` (`index.tex`, `test.tex`, etc.).

Le convertisseur par défaut de MkDocs est Python Markdown. C'est également ce module utilisé en interne si le fichier d'entrée est du Markdown.

Voici un exemple comment Python Markdown est utilisé en interne:



## CLI

Le cli texsmith permet de convertir un fichier Markdown ou un fichier HTML issu de MkDocs ou Python Markdown en LaTeX.

```bash
texsmith convert docs/index.md -o output/ # default is output/
texsmith convert docs/index.html -o output/
```

Les options possibles sont :

- `-h,--heading-level` : permet d'indenter tous les niveaux (section -> subsection) si le document intervient dans un document plus général.
- `-o,--output-dir` : répertoire de sortie où sont également copiés les artefacts (téléchargement des images sur internet, conversion des svg, drawio, mermaid en pdf, toutes les images en png).
- `-a,--copy-assets` : Oui ou non copier et générer les assets (images, documents dans les hyperref).
- `-m,--manifest` : Générer un fichier de manifeste des assets inclus.
- `-t,--template` : Spécifier le template LaTeX à utiliser pour la conversion. Soit un chemin vers un dossier local, soit le nom du package PIP à utiliser i.e. `texsmith-template-foobar`, tu utilises `-t foobar`.
- `--debug` : Activer le mode debug pour sauvegarder les fichiers intermédiaires (HTML, logs, etc.).
- `-e,--markdown-extensions` : Liste des extensions Markdown à utiliser lors de la conversion (séparées par des virgules ou des espaces, ou des caractères null) i.e. `-e pymdownx.superfences,pymdownx.highlight,caret`.

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

## TO-DO

- [x] Remplacer safe_quote par requote_url de requests.utils
- [x] Remplacer fonctions helpers par package latexcodec
- [x] Remplacer to_kebab_case par python-slugify
- [x] Documenter class RenderPhase(Enum): chaque état et pourquoi.
- [x] Supporter la langue (babel) selon la configuration (polyglossia à venir)
- [x] Permettre l'écritre d'extensions Renderer,formatter (demo counter)
- [x] Support for index generation (makeindex, xindy)
- [ ] Rename package texsmith et les templates texsmith-template-*
- [ ] Utiliser verbatim par défaut, les templates peuvent overrider cela
- [ ] Gérer les assets de manière centralisée (images, drawio, mermaid...)
- [ ] Ajouter des tests unitaires et d'intégration pour le CLI et MkDocs
- [ ] Documenter le processus de création de templates LaTeX personnalisées
- [ ] Declare solution/exercises in a plugin way
- [ ] Find a way to have a solid and robust docker submodule/class
- [ ] Convert some journals templates (Springer, Elsevier, IEEE...)
- [ ] Support for bibliography (biblatex, natbib...)

- [ ] Support for glossaries (glossaries package)
- [ ] Support for cross-references (cleveref package)
- [ ] Add more Markdown extensions (footnotes, definition lists, tables...)
- [ ] Improve error handling and reporting during LaTeX compilation
- [ ] Optimize asset conversion and caching mechanisms
- [ ] Mkdocs Integration
  - [ ] Support extensions in other MkDocs plugin (add latex syntax, transformers...)
