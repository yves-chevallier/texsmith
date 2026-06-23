# Refactoring TeXSmith — HTML implicite → IR typée multi-backend

> Dossier de pilotage de la migration. **Ne contient pas de code de production** : uniquement
> le plan, les rôles d'agents, le workflow d'orchestration et le suivi vivant.

## Pourquoi

Aujourd'hui TeXSmith n'a **pas de représentation intermédiaire**. L'arbre BeautifulSoup
*est* l'IR : les handlers mutent l'arbre en place en y injectant des chaînes LaTeX
(`element.replace_with(NavigableString(latex))`), puis `soup.get_text()` aplatit le tout
([renderer.py:205](../src/texsmith/adapters/latex/renderer.py#L205)). Le HTML porte donc
trois rôles incompatibles : sortie de Markdown, structure traversée, **et** conteneur de
sémantique LaTeX (`data-ts-colspec="lrX"`, `<ts-marginnote>`, `data-tex-command="\LaTeX"`…).

Conséquence : impossible de brancher un second backend (Typst) sans dupliquer ~4000 lignes
de handlers. **L'IR n'est pas un confort, c'est la condition du multi-backend.**

## Cible

```
        READERS                     IR (typée, sémantique,            WRITERS
                                     SANS notion de backend)
Markdown ─(md+ext)─► HTML ─► HtmlReader ─►  ┌──────────────┐  ─► LaTeXWriter ─► .tex/PDF
HTML (MkDocs) ──────────────► HtmlReader ─► │  Block/Inline │  ─► TypstWriter ─► .typ/PDF
                                            └──────────────┘  ─► (HtmlWriter, …)
```

Pivot conceptuel : **le HTML redevient un simple *format d'entrée* (un reader parmi
d'autres)** ; il cesse d'être le substrat de transformation. On garde ainsi tout
l'investissement Material/pymdownx tout en découplant la sortie.

## Principes directeurs (non négociables)

1. **Modulaire mais pas dispersé.** On *remplace* les handlers existants, on ne les
   double pas. `adapters/handlers/*` et la partie « émission LaTeX » de `extensions/*/renderer.py`
   sont **supprimés** au fur et à mesure que leur logique migre vers `readers/` et `writers/`.
   Net : à la fin, *moins* de chemins de code, pas plus.
2. **Pas de compatibilité ascendante.** TeXSmith n'est pas releasé. L'API peut bouger.
   On ne crée **aucun** shim, alias, ni couche de compat (cf. `AGENT.md`). Les shims
   actuels (`_FallbackConverter`, modules top-level `progressbar.py`/`texlogos.py`/…) sont
   supprimés en Phase 5.
3. **Les exemples font foi.** `examples/*`, les snippets (`examples/snippet`,
   `adapters/plugins/snippet.py`) et la doc MkDocs doivent produire un rendu **équivalent**
   avant/après. Le filet de sécurité est le *golden harness* (Phase 0) : diff du `.tex`
   généré, normalisé pour ignorer dates/versions/hashes/chemins.
4. **Les tests sont ajustables, le rendu non.** Les tests qui assertent sur la *mécanique
   interne* (noms de handlers, `@renders`, structure du soup) seront réécrits pour la
   nouvelle architecture. Les tests qui assertent sur le *LaTeX produit* doivent rester
   verts (ou être resserrés, jamais relâchés).
5. **Une IR sémantique, pas LaTeX-déguisée.** Un `Table` porte `Alignment.RIGHT`, jamais
   `"r"` ni `"lrX"`. C'est le writer qui calcule le préambule. Aucune chaîne backend dans l'IR
   (hors nœud d'échappatoire explicite `RawBlock(format=...)`).

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `README.md` | Ce fichier : vision, principes. |
| `PLAN.md` | Les phases, leur périmètre, critères d'entrée/sortie, risques. |
| `agents.md` | Rôles des agents + prompts prêts à coller. |
| `workflow.md` | Orchestration : séquençage, gates, parallélisme, hand-offs. |
| `PROGRESS.md` | Suivi vivant. **Tout agent met à jour ce fichier** en fin de tâche. |

Artefacts générés pendant la migration (non versionnés dans le plan) :
- `refactoring/baseline/` — snapshots `.tex` de référence (Phase 0).
- `refactoring/tools/` — harnais de snapshot/diff (Phase 0).

## Démarrage rapide

1. Lire `PLAN.md` puis `workflow.md`.
2. Lancer l'agent **Golden Harness** (Phase 0) — rien d'autre ne commence avant que le
   filet existe.
3. Suivre le séquençage de `workflow.md`. Chaque phase est *gatée* par le golden diff == 0.
</content>
</invoke>
