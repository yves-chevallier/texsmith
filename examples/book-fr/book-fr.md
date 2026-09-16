---
title: Petit traité de typographie
subtitle: Un livre français de démonstration
author: Ada Lovelace
date: 2026-01-15
press:
  paper: a5
  template: book
  language: fr
  base_level: part
  slots:
    preface: Préface
---
## Préface

Ce livre existe pour une seule raison : vérifier que le gabarit `book` se
compose en français. La table des matières numérote ses parties avec le nom
ordinal que `babel-french` fabrique — « Première partie », « Deuxième partie » —
et les colonnes de la table doivent être mesurées avec ce nom-là.

# Les caractères

## L'alphabet

Le français ajoute à l'alphabet latin des lettres accentuées : à, â, ç, é, è,
ê, ë, î, ï, ô, ù, û, ü, ÿ, ainsi que les ligatures œ et æ.

## La ponctuation

La ponctuation haute — le point-virgule, les deux-points, le point
d'interrogation et le point d'exclamation — demande une espace fine
insécable. Les guillemets français encadrent la citation : « ainsi ».

### Les guillemets

Une citation dans une citation se marque avec les guillemets anglais :
« il a dit “non” puis il est parti ».

# Les mesures

## Le cicéro

Le cicéro vaut douze points Didot, soit 4,512 mm. Le point pica anglo-saxon,
lui, vaut 0,3528 mm.

## Le corps

| Usage | Corps | Interligne |
| --- | --- | --- |
| Note | 8 pt | 10 pt |
| Texte | 10 pt | 12 pt |
| Titre | 14 pt | 16 pt |

Une formule pour finir : $c = 12 \times d$, où $d$ est le point Didot.
