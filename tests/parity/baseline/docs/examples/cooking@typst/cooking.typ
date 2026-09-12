#set document(
title: "Cooking Recipes",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Cooking Recipes]]
#v(1.5em)

TeXSmith isn’t just for papers and slides – it can plate up gorgeous recipes straight from structured data. Here’s a French walnut cake expressed as YAML, pushed through a custom `recipe` template. Click the card to grab the PDF.

#figure(
image("snippet-<HASH>.png", width: 60%),
caption: [Demo],
)

The authoring surface is pure data: *YAML* fields flow into a #ts-logo("LaTeX") template, no Markdown gymnastics required. Swap the YAML for a DB/API payload and you’ve got a pipeline-ready recipe generator for your site or app.

#ts-div("tab", title: "cake.yml")[
```yaml
---
title: Gâteau aux noix
description: |
  Ce gâteau aux noix séduit dès la première bouchée par son équilibre parfait
  entre une pâte sablée délicatement friable et une farce généreuse mêlant
  noix croquantes, caramel doré et miel parfumé. Doux sans être lourd,
  riche sans être écœurant, il offre une texture fondante relevée par
  le croustillant des noix et la profondeur du caramel. Servi tiède
  ou à température ambiante, il dégage un parfum chaleureux et
  gourmand qui évoque les desserts traditionnels d'automne, tout en
  offrant une élégance rustique irrésistible. Une véritable tentation
  pour tous les amateurs de saveurs authentiques et de pâtisseries raffinées.
notes: >
  Se conserve env. 2 semaines au réfrigérateur bien emballé.
time:
  total: 140
  preparation: 50
  cooking: 40
sections:
  - title: Préparation du moule
    instructions:
      - Préparer le moule.
  - title: Pâte sablée
    steps:
      - ingredients:
          - quantity:
              amount: 150
              unit: g
            name: farine
          - quantity:
              amount: 100
              unit: g
            name: sucre
          - quantity:
              amount: 1
              unit: pincée
            name: sel
        instructions:
          - Mettre dans un saladier.
      - ingredients:
          - quantity:
              amount: 100
              unit: g
            name: beurre froid
        instructions:
          - Couper en morceaux, ajouter.
          - <
            Travailler soigneusement à la main jusqu'à ce que la préparation
            soit friable.
      - ingredients:
          - quantity:
              amount: 1
            name: œuf
        instructions:
          - Ajouter.
          - Travailler rapidement à la main, ne pas pétrir.
          - Couvrir et mettre au réfrigérateur 30 minutes.
        time:
          refrigeration: 30
  - title: Farce
    steps:
      - ingredients:
          - name: noix
            quantity:
              amount: 130
              unit: g
        instructions:
          - Hacher grossièrement, réserver.
      - ingredients:
          - quantity:
              amount: 100
              unit: g
            name: sucre
          - quantity:
              amount: 2
              unit: cs
            name: eau
        instructions:
          - Verser dans une grande casserole.
          - Chauffer à feu très vif jusqu'à dissolution du sucre, revenir à feu vif.
          - Tourner légèrement la casserole.
          - Faire caraméliser sans remuer jusqu'à ce que la couleur devienne noisette.
          - Retirer la casserole du feu.
      - ingredients:
          - quantity:
              amount: 1.25
              unit: dl
            name: crème entière
        instructions:
          - Ajouter, mélanger à la cuillère de cuisine.
          - <
            Réchauffer à petit feu en remuant jusqu'à dissolution complète du
            caramel, porter à ébullition env. 10 min.
        time:
          cooking: 10
      - ingredients:
          - name: miel liquide
            quantity:
              amount: 1.5
              unit: cs
        instructions:
          - Ajouter, mélanger, laisser refroidir.
  - title: Assemblage
    steps:
      - ingredients:
          - name: farine
            quantity:
              text: un peu
        instructions:
          - Partager la pâte en 3 portions régulières.
          - <
            Étaler 1 portion en un cercle d'environ 4 mm d'épaisseur sur un peu de
            farine.
          - Poser dans le moule préparé.
          - Piquer avec une fourchette.
      - ingredients:
          - name: farine
            quantity:
              text: un peu
        instructions:
          - Former un rouleau avec la deuxième portion de pâte.
          - Appuyer sur les bords du moule jusqu'à obtenir un bord d'environ 4 cm de
            hauteur.
      - instructions:
          - Répartir la farce sur le fond de pâte.
          - Replier le bord qui dépasse sur la farce.
          - <
            Étaler la dernière portion en un cercle d'environ 4 mm et poser sur la
            farce.
          - Piquer avec une fourchette.
          - Cuire dans le bas du four, 200°C, 40-50 min.
        time:
          cooking: 40
---
```]

#ts-div("tab", title: "manifest.toml")[
```toml
[compat]
texsmith = ">=0.6,<1.0"

[latex.template]
name = "recipe"
version = "0.1.0"
entrypoint = "template.tex"
engine = "lualatex"
texlive_year = 2023
tlmgr_packages = [
    "geometry",
    "fontspec",
    "pgf",
    "tabularx",
    "multirow",
    "xcolor",
]

[latex.template.assets]
"tikz-cookingsymbols.sty" = { source = "tikz-cookingsymbols.sty" }

[latex.template.slots.mainmatter]
default = true

[latex.template.attributes.preamble]
default = ""
type = "string"
allow_empty = true

# --------------------------------------------------------------------------- #
# Typst backend: a native recipe card rendered directly from the YAML front
# matter (data-driven, like the LaTeX template — the document body is unused).
# --------------------------------------------------------------------------- #
[typst.template]
name = "recipe"
version = "0.1.0"
entrypoint = "template.typ"

[typst.template.slots.mainmatter]
default = true

[typst.template.attributes.preamble]
default = ""
type = "string"
allow_empty = true
```]

#ts-div("tab", title: "template.tex")[
```tex
\documentclass{article}
\usepackage[a4paper, top=2cm, left=2cm, right=2cm, bottom=1cm]{geometry}
\usepackage{fontspec}
\usepackage{tikz-cookingsymbols}
\usepackage{tabularx}
\usepackage{multirow}
\usepackage{enumitem}
\usepackage{array}
\BLOCK{ if extra_packages }
\VAR{extra_packages}
\BLOCK{ endif }

\BLOCK{ if preamble }
\VAR{preamble}

\BLOCK{ endif }

\setlist[itemize]{leftmargin=*,nosep}
\renewcommand{\familydefault}{\sfdefault}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.5em}

\newlength{\colA}
\newlength{\colB}
\setlength{\colA}{0.07\textwidth}
\setlength{\colB}{0.15\textwidth}
\newcolumntype{A}{>{\raggedright\arraybackslash}p{\colA}}
\newcolumntype{B}{>{\raggedright\arraybackslash}p{\colB}}
\newcolumntype{C}{>{\raggedright\arraybackslash}X}

\BLOCK{ macro quantity(value) -}
\BLOCK{ if value is mapping -}
  \BLOCK{ if value.text -}
    \VAR{value.text}
  \BLOCK{ elif value.amount is defined -}
    \VAR{value.amount}\BLOCK{ if value.unit }~\VAR{value.unit}\BLOCK{ endif }
  \BLOCK{ else -}
  \BLOCK{ endif -}
\BLOCK{ elif value is number -}
  \VAR{value}
\BLOCK{ elif value -}
  \VAR{value}
\BLOCK{ endif -}
\BLOCK{ endmacro }

\BLOCK{ set recipe_documents = documents | default([], true) }

\begin{document}
\pagestyle{empty}
\BLOCK{ if recipe_documents }
\BLOCK{ for doc in recipe_documents }
\BLOCK{ set data = doc.front_matter | default({}, true) }
\BLOCK{ set recipe = data.recipe if data.recipe is defined else data }
\BLOCK{ if loop.index > 1 }\newpage\BLOCK{ endif }

{\Huge\bfseries \VAR{recipe.title | default('Recette', true)}}\par
\vspace{2cm}
\noindent
\begin{minipage}[t]{0.3\textwidth}
\vspace{0pt}%
\rule{\linewidth}{1.5pt}
\BLOCK{ set time = recipe.time | default({}, true) }
\TopBottomHeat\quad{} temps total \textbf{\VAR{time.total | default('--', true)}}~min \\
\Grill\quad{} préparation \textbf{\VAR{time.preparation | default('--', true)}}~min \\
\ConvectionOven\quad{} cuisson \textbf{\VAR{time.cooking | default('--', true)}}~min \\
\rule{\linewidth}{1.5pt}

\BLOCK{ if recipe.description }
\subsection*{Description}
\VAR{recipe.description}
\BLOCK{ endif }

\subsection*{Conseils}

\VAR{recipe.notes | default('Aucun conseil enregistré.', true)}

\end{minipage}
\hfill
\begin{minipage}[t]{0.68\textwidth}
\vspace{0pt}%
\BLOCK{ for section in recipe.sections | default([], true) }
\textbf{\VAR{section.title | default('Étape', true)}}\vskip 0.75em

\BLOCK{ if section.instructions }
\begin{itemize}
\BLOCK{ for instruction in section.instructions }
  \item \VAR{instruction}
\BLOCK{ endfor }
\end{itemize}
\BLOCK{ endif }

\BLOCK{ if section.steps }
\begin{tabularx}{\textwidth}{@{}A B C@{}}
\BLOCK{ for step in section.steps }
\BLOCK{ set raw_items = step.ingredients | default([], true) }
\BLOCK{ if raw_items is mapping }
  \BLOCK{ set ingredients = [raw_items] }
\BLOCK{ elif raw_items is iterable and raw_items is not string }
  \BLOCK{ set ingredients = raw_items }
\BLOCK{ else }
  \BLOCK{ set ingredients = [] }
\BLOCK{ endif }
\BLOCK{ set note = step.instructions | default([], true) }
\BLOCK{ set note_text = note | join(' \\newline ') }
\BLOCK{ if ingredients }
  \BLOCK{ for ingredient in ingredients }
    \VAR{quantity(ingredient.quantity | default('', true))} &
    \VAR{ingredient.name | default(ingredient.step | default('', true), true)} &
    \BLOCK{ if loop.first }
      \VAR{note_text}
    \BLOCK{ endif }\\
  \BLOCK{ endfor }
\BLOCK{ else }
  & & \VAR{note_text}\\
\BLOCK{ endif }
\BLOCK{ if not loop.last }
\multicolumn{3}{@{}l}{\rule{\textwidth}{0.2pt}}\\
\BLOCK{ endif }
\BLOCK{ endfor }
\end{tabularx}
\BLOCK{ endif }

\vspace{1em}
\BLOCK{ endfor }
\end{minipage}

\BLOCK{ endfor }
\BLOCK{ endif }

\BLOCK{ if mainmatter and mainmatter.strip() }
\newpage
\VAR{mainmatter}
\BLOCK{ endif }

\end{document}
```]

#ts-callout(kind: "note")[
The recipe layout used in this template was inspired by the Cours de cuisine created by M.-C. Bolle back in 1978. She produced an exceptional cookbook for the Department of Public Instruction of the Canton of Geneva, Switzerland.

I’ve never seen recipes presented quite this way anywhere else – it’s a uniquely clever system – but I find it incredibly practical and efficient.]
