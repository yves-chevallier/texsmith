# Workflow d'orchestration

## Principe

Migration **gatée par phase**. Le golden harness est l'arbitre objectif : on ne franchit un
GATE que si `snapshot.py diff == 0` + `pytest` vert + revue GO. Deux agents sont *persistants*
(Architect/IR Owner, Golden Harness Engineer) : on les **relance via SendMessage** pour
conserver leur contexte, plutôt que d'en créer de nouveaux.

## Séquençage

```
            ┌──────────────────────────────────────────────────────────────┐
            │  P0  Golden Harness Engineer          (seul, bloquant)         │
            └──────────────────────────────────────────────────────────────┘
                                    │ GATE: baseline figée, diff vide
                                    ▼
            ┌──────────────────────────────────────────────────────────────┐
            │  P1  Architect / IR Owner             (seul)                   │
            └──────────────────────────────────────────────────────────────┘
                                    │ GATE: contrat IR figé dans PROGRESS.md
                                    ▼
            ┌───────────────────────────────┐   ┌───────────────────────────┐
            │  P2  Reader Agent  (HTML→IR)   │ ∥ │ P3 Writer Agent (IR→LaTeX) │
            └───────────────────────────────┘   └───────────────────────────┘
                                    │ GATE COMMUN: parité golden == 0
                                    │ (arbitrage IR Owner sur frictions ; Reviewer GO/NO-GO)
                                    ▼
            ┌───────────────────────────────┐   ┌───────────────────────────┐
            │  P4  Writer Agent (Typst)      │   │ P5 Cleanup Agent           │
            │  (reader/IR figés)             │ ~ │ (golden doit rester à 0)   │
            └───────────────────────────────┘   └───────────────────────────┘
                                    │ GATE: Typst subset OK + golden LaTeX == 0
                                    ▼
                              Revue finale (Reviewer)
```

`∥` = parallèle strict. `~` = chevauchement toléré une fois la parité atteinte (P5 ne doit
jamais introduire d'écart golden).

## Le point délicat : le Core swap (P2 ∥ P3)

Reader et Writer travaillent **en parallèle contre le contrat IR figé**. Pour éviter les
collisions et les blocages mutuels :

1. **Geler le contrat d'abord.** L'IR Owner publie `ir/nodes.py` + la section « Contrat IR
   figé » de `PROGRESS.md` *avant* que P2/P3 démarrent. C'est l'interface partagée.
2. **Isolation par worktree.** Reader (`src/texsmith/readers/`) et Writer
   (`src/texsmith/writers/`) touchent des répertoires disjoints → lancer chaque agent en
   `isolation: "worktree"` pour éviter les conflits, puis intégrer.
3. **Stub d'amorçage.** Tant que le Reader n'émet pas tous les nœuds, le Writer teste contre des
   arbres IR construits à la main (fixtures). Symétriquement, le Reader se valide en sérialisant
   l'IR (repr) sans dépendre du Writer. Les deux ne se bloquent jamais.
4. **Branchement final.** Le remplacement du pipeline dans `core/conversion/` (mutate+get_text →
   read+write) est fait par le **Writer Agent** une fois le Reader complet, en un seul commit, puis
   passé au golden.
5. **Frictions de contrat.** Toute demande de modif de l'IR passe par la section « Frictions
   contrat IR » de `PROGRESS.md` → l'IR Owner arbitre (SendMessage) → met à jour le contrat et
   notifie les deux.

## Cadence des GATES

| Après | Qui lance le GATE | Critère |
|---|---|---|
| P0 | Golden Harness | `capture` puis `diff` vide ; `make examples` (tectonic, non-Docker) OK |
| P1 | IR Owner + pyright | types + tests verts ; contrat publié |
| P2∥P3 | Golden Harness + Reviewer | `diff == 0` sur tous exemples/snippets/MkDocs ; pytest vert ; handlers supprimés ; GO |
| P4 | Golden Harness | subset Typst compile ; golden LaTeX == 0 |
| P5 | Golden Harness + Reviewer | golden == 0 ; métriques smell en baisse ; GO |

## Coordination & traçabilité

- **`PROGRESS.md` est le bus de communication.** Chaque agent y écrit son état, ses blocages, le
  verdict des GATES. Pas de canal hors-bande.
- **Branches.** Une branche par phase (`refactor/p0-golden`, `refactor/p1-ir`,
  `refactor/core-swap`, `refactor/p4-typst`, `refactor/p5-cleanup`). Merge après GO du Reviewer.
- **Commits.** Petits, gatés. Ne jamais committer un état où le golden régresse (sauf WIP isolé en
  worktree non mergé).

## Deux manières de lancer concrètement

**Option A — pilotage manuel (recommandé pour démarrer).**
Lancer un agent par phase avec le prompt correspondant de `agents.md`. Pour P2∥P3, lancer Reader
et Writer dans le même message (worktrees séparés). Relancer Architect et Golden Harness via
SendMessage aux moments prévus. Lire chaque résultat, mettre à jour `PROGRESS.md`, décider le
GATE, puis passer à la phase suivante.

**Option B — orchestration par Workflow (si vous optez pour le multi-agent automatisé).**
Un script Workflow par milestone, jamais un seul pour tout (vous devez rester dans la boucle aux
GATES) :
- `wf-core-swap` : `phase('Reader')` et `phase('Writer')` en `parallel(...)` contre le contrat IR,
  puis une étape `phase('Parity')` qui boucle `snapshot diff` jusqu'à 0 ou budget épuisé, puis une
  étape Reviewer adverse. Chaque agent en `isolation: 'worktree'`.
- Ne déclencher l'option B que sur demande explicite (« use a workflow »). Sinon, Option A.

## Critère de fin global

- Golden `diff == 0` partout (LaTeX), exemples + snippets + MkDocs au rendu équivalent.
- `TypstWriter` produit un sous-ensemble compilable — la preuve que l'IR est réellement
  multi-backend.
- Surface de code en **baisse** (handlers/renderers/shims supprimés), métriques de smell en
  baisse, archi lisible : Readers / IR / Writers, trois étages nets.
</content>
