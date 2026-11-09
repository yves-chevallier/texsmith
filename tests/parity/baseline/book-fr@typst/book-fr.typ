#set document(
title: "Petit traité de typographie",
author: ("Ada Lovelace"),
)
#set page(
paper: "a5",
margin: 2cm,
numbering: "1",
)
#set text(font: "New Computer Modern", size: 10pt, lang: "fr")
#set list(marker: [–])
#set par(justify: true)
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => [
#pagebreak(weak: true)
#v(2em)
#text(size: 1.8em, weight: "bold")[#it]
#v(1em)]

#align(center + horizon)[
#text(size: 2.4em, weight: "bold")[Petit traité de typographie]
#v(0.5em)
#text(size: 1.4em)[Un livre français de démonstration]
#v(2em)
#text(size: 1.2em)[Ada Lovelace]#linebreak()
#v(1em)
#text[15 janvier 2026]]
#pagebreak()

#outline()
#pagebreak()

#ts-callout-style.update("fancy")

== Préface

Ce livre existe pour une seule raison : vérifier que le gabarit `book` se
compose en français. La table des matières numérote ses parties avec le nom
ordinal que `babel-french` fabrique — « Première partie », « Deuxième partie » —
et les colonnes de la table doivent être mesurées avec ce nom-là.

= Les caractères

== L'alphabet

Le français ajoute à l'alphabet latin des lettres accentuées : à, â, ç, é, è,
ê, ë, î, ï, ô, ù, û, ü, ÿ, ainsi que les ligatures œ et æ.

== La ponctuation

La ponctuation haute — le point-virgule, les deux-points, le point
d'interrogation et le point d'exclamation — demande une espace fine
insécable. Les guillemets français encadrent la citation : « ainsi ».

=== Les guillemets

Une citation dans une citation se marque avec les guillemets anglais :
« il a dit “non” puis il est parti ».

== Les énumérations

Une liste se compose avec le tiret demi-cadratin, et non avec la puce :

- chaque élément s'ouvre sur un tiret ;
- un élément imbriqué garde le même tiret :
- à tous les niveaux ;
- le dernier élément se termine par un point.

= Les mesures

== Le cicéro

Le cicéro vaut douze points Didot, soit 4,512 mm. Le point pica anglo-saxon,
lui, vaut 0,3528 mm.

== Le corps

#table(
columns: (1fr, 1fr, 1fr),
align: (left, left, left),
table.header([Usage], [Corps], [Interligne]),
[Note], [8 pt], [10 pt],
[Texte], [10 pt], [12 pt],
[Titre], [14 pt], [16 pt],
)

Une formule pour finir : #mi(`c = 12 \times d`), où #mi(`d`) est le point Didot.
