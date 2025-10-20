On va rajouter au cli mkdocs_latex :

-h,--heading-level permettant d'indenter tous les niveau (section -> subsection) si le document intervient dans un document plus général
-o,--output-dir répertoire de sortie ou sont également copiés les artefacts (téléchargement des images sur internet, conversion des svg, drawio, mermaid en pdf, toutes les images en png)
-a,--copy-assets Oui ou non copier et générer les assets (images, documents dans les hyperref)



Les attributs propres à un document sont :

- Titre
- Sous-titre
- Auteur(s)
- Année




tag
  .where('classes': ('highlight'))
  .where_not(classes=('~mermaid',))
  .find('code', else=lambda: InvalidNodeError("Missing <code> element inside highlighted block"))
  .


J'aimerais ajouter le support pour un nouveau type de tag. J'aurais besoin de définir un nouveau renderer


def render_code_blocks(element: Tag, context: RenderContext) -> None:
    """Render MkDocs-highlighted code blocks."""

    classes = element.get("class") or []
    if "highlight" not in classes:
        return
    if "mermaid" in classes:
        return

    code_element = element.find("code")
    if code_element is None:
        raise InvalidNodeError("Missing <code> element inside highlighted block")
    code_classes = code_element.get("class") or []
    if any(cls in {"language-mermaid", "mermaid"} for cls in code_classes):
        return

    if _looks_like_mermaid(code_element.get_text(strip=False)):
        return

    language = _extract_language(code_element)
    lineno = element.find(class_="linenos") is not None

    filename = None
    if filename_el := element.find(class_="filename"):
        filename = filename_el.get_text(strip=True)

    listing: list[str] = []
    highlight: list[int] = []

    spans = code_element.find_all("span", id=lambda value: bool(value and value.startswith("__")))
    if spans:
        for index, span in enumerate(spans, start=1):
            highlight_span = span.find("span", class_="hll")
            current = highlight_span or span
            if highlight_span is not None:
                highlight.append(index)
            listing.append(current.get_text(strip=False))
        code_text = "".join(listing)
    else:
        code_text = code_element.get_text(strip=False)

    baselinestretch = 0.5 if _is_ascii_art(code_text) else None
    code_text = code_text.replace("{", r"\{").replace("}", r"\}")

    latex = context.formatter.codeblock(
        code=code_text,
        language=language,
        lineno=lineno,
        filename=filename,
        highlight=highlight,
        baselinestretch=baselinestretch,
    )

    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)

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

Le code LaTeX généré ne contient pas de balises `\begin{document}` ni de préambule `\documentclass{...}`. Cela permet d'insérer le contenu généré dans un document LaTeX plus large. Pour constuire un document complet, il est nécessaire de spécifier `--template` lors de l'appel à la commande `mkdocs_latex convert`.

Le templates sont des packets PIP nommés `mkdocs-latex-template-<nom>` ou des dossiers locaux contenant les fichiers nécessaires.

Templates LaTeX

On peut avoir des templates associables:
- template.tex
- classe.cls (et d'autres fichiers si nécessaire)

Selon la template on ne va pas rendre certains éléments de la même manière:
- Utiliser verbatim pour le code
- Utiliser minted/listing...
- Rendre les emoji fontawesome avec usepackage fontawesome
- La manière d'insérer une figure (caption en haut, en bas...)
- La numérotation ou non des chapitres

De manière modulaire on peut simplement imaginer qu'un "nouveau" template latex n'est qu'une collections de fichiers:
- .cls, .sty
- template.tex (jinja)
- assets additionnels (image, logo...)
- des fonts
- une version de texlive
- la liste des paquets tlmgr nécessaires
- des override des templates du parseur (acronym.tex, add.tex...) (jinja)

On peut avoir des hooks pré/post pour par exemple ne pas copier tous les assets: exemple de cover qui nécessite tel ou tel logo?

Depuis le cli on pourrait avoir la possibilité de spécifier le thème latex utilisé soit :

- en donnant un dossier contenant le template, la structure doit être rigide, mais il faut bien documenter
- pip install mkdocs-latex-template-<nom>

Structure rigide avec cookiecutter, manifest simple...
https://chatgpt.com/share/68f54264-3e78-800b-9f16-0db8bd5c892b

------



## Conversion Markdown/HTML

Le convertisseur par défaut de MkDocs est Python Markdown. C'est également ce module utilisé en interne si le fichier d'entrée est du Markdown.

Voici un exemple comment Python Markdown est utilisé en interne:

```python
import markdown

md = markdown.Markdown(extensions=[
    'pymdownx.superfences',   # remplace fenced_code
    'pymdownx.highlight',     # coloration + options sympas
    # ... d’autres extensions si besoin
])

html = md.convert("```python\nprint('Hello')\n```")
print(html)
```

## CLI

Le cli mkdocs_latex permet de convertir un fichier Markdown ou un fichier HTML issu de MkDocs ou Python Markdown en LaTeX.

```bash
mkdocs_latex convert docs/index.md -o output/ # default is output/
mkdocs_latex convert docs/index.html -o output/
```

Les options possibles sont :

- `-h,--heading-level` : permet d'indenter tous les niveaux (section -> subsection) si le document intervient dans un document plus général.
- `-o,--output-dir` : répertoire de sortie où sont également copiés les artefacts (téléchargement des images sur internet, conversion des svg, drawio, mermaid en pdf, toutes les images en png).
- `-a,--copy-assets` : Oui ou non copier et générer les assets (images, documents dans les hyperref).
- `-m,--manifest` : Générer un fichier de manifeste des assets inclus.
- `-t,--template` : Spécifier le template LaTeX à utiliser pour la conversion. Soit un chemin vers un dossier local, soit le nom du package PIP à utiliser i.e. `mkdocs-latex-template-foobar`, tu utilises `-t foobar`.
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
