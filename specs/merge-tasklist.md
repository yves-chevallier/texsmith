# Merge tasklist — autoriser le merge tmark → main et texsmith → master

Objectif : quand chaque case est cochée, le merge est autorisé et une release
peut être taguée. Une case n'est cochée qu'après vérification objective
(commande, test ou diff nommé). Mis à jour au fil du travail, dernière mise à
jour : 2026-09-14.

Ordre imposé : tmark merge d'abord, puis texsmith, puis les six lignes
`ref: texsmith-migration` de `.github/workflows/*.yml` deviennent un tag.

## 0. Sauvegarde

- [x] tmark `texsmith-migration` poussée sur GitHub (2026-09-14).
- [x] texsmith `tmark-migration`, `refactor/00`, `03`, `05`, `08`, `07` poussées sur GitHub (2026-09-14).

## 1. Correctifs tmark (bloquants)

- [x] **Échappement Typst** : `//` et `/*` cassés, `= + - /` en début de ligne
      et `~` échappés (`crates/tmark-writers/src/typst/escape.rs`), fixture de
      conformance, snapshots relus. Fusionné dans `texsmith-migration` (0424387), vérifié au compilateur typst 0.15.1.
- [x] **Sémantique des citations** : un `@key` nu rend la citation courte
      (`\cite` / `#cite(key)`) par défaut ; une clé de front matter bascule en
      narratif (`\textcite` / `form: "prose"`) ; `@[key]` reste parenthétique ;
      spec §Citations et `12-spec-challenges.md` mis à jour ; fixtures et
      snapshots. Fusionné (4593a6b) : feature `press.features: {citations.narrative: true}`, drapeaux `@[+key]` / `@[-key]`, C51.
- [x] Les deux branches fusionnées dans `texsmith-migration`, `cargo test`
      (331), `clippy -D warnings`, `fmt --check`, artefacts générés à jour.

## 1b. Défauts trouvés en vérifiant

- [x] Le fix `[^key]` → `@key` colle la citation au mot précédent (`sortie@key` reste littéral, 21/29 citations perdues sur bien-air/review). Corrigé dans 4593a6b : le fixer insère l'espace.
- [ ] Le sucre `++…++` avale « C++03 … C++ » en prose ; reconnaissance resserrée. Branche `fix/keystroke`.

## 2. Revue de la spec

- [x] Revue de conformité indépendante spec ↔ code sur C27–C50
      (`design/reviews/07-spec-conformance-migration.md`) : 0 bloquant, 11 majeurs, 14 mineurs. Correction en cours sur `fix/spec-text` et `fix/spec-code`.
- [x] Revue de cohérence interne de `spec/tmark.md` comme spécification de
      langage (`design/reviews/08-spec-consistency.md`, 8e8dbce) : 5 bloquants, 15 majeurs, 19 mineurs.
- [ ] Chaque finding classé : corrigé, reporté avec numéro de challenge, ou
      rejeté avec raison. Texte de la spec : fait (c3bf402, B1–B5, M1–M15, F3–F5, C52–C60).
      Code (F1, F2, F7, F8, F10, C27, C60) : branche `fix/spec-code` en cours.

## 3. Correctifs texsmith

- [x] Les 24 `warnings.warn` routés par `emit_diagnostic` avec un code, ou
      supprimés avec raison ; `--strict` et `--diagnostics-json` les voient.
      Fait (d6b2e0a) : 12 routés (`font-fallback`, `fragment-manifest`, `metadata-invalid`), 11 sur logger de module
      faute d'émetteur atteignable, 1 `UserWarning` gardé pour les auteurs de templates. 1345 tests.
- [ ] Baseline de parité ré-enregistrée après le fix des citations, diff lu
      ligne par ligne (`scripts/parity.py baseline --check`).
- [ ] `docs/syntax/references.md`, `docs/guide/migration.md` et
      `CHANGELOG.md` décrivent la sémantique des citations et l'option.
- [ ] `DocumentState` purgé de ses 7 champs et 4 méthodes morts.
- [ ] `_LegacyContext` / `runtime[...]` de `passes/assets.py` remplacés par
      une signature typée depuis `PassContext`.
- [ ] Cycle `passes` ↔ `core.conversion` cassé ; les imports locaux qui
      l'absorbaient remontés au niveau module.
- [ ] `unicodeblocks` retiré de `pyproject.toml` (déjà inutilisé en 0.6.0) ;
      `pyxindy` conservé (index via `adapters/latex/pyxindy.py`) ;
      `beautifulsoup4` et `pylatexenc` évalués.
- [ ] `wheel_schema_mismatch()` appelé au démarrage (tmark importé par le
      reader) et testé.

## 4. Fonctionnalités à garantir

- [x] Compteurs personnalisés : `~/bien-air/review` (`counters: fw`,
      `#{fw:key}`, `@fw:key`) passe `tmark lint --fix` et se construit en PDF
      avec les mêmes numéros ; documenté dans `docs/syntax/counters.md` (80cbcb0). Vérifié : 47 marqueurs et 140 renvois identiques avant/après fixer.
- [x] Substitution de fontes XeLaTeX / passe `scripts` : un document CJK +
      grec + arabe se construit avec les mêmes `\tsscript` qu'en 0.6.0. Vérifié : déclarations `\newfontfamily` identiques, texte PDF identique.
- [x] Numérotation site-wide et index dans le plugin MkDocs unique, vérifiés
      sur `examples/mkdocs`. Vérifié : FW-01/FW-02 continus entre pages, liens inter-pages, `ts-index` + tags de recherche, export PDF identique, alias legacy avec warning.

## 5. Nettoyage des artefacts de migration

- [x] tmark : 14 worktrees `~/tmark-wt/*` et leurs branches `wt/*` supprimés
      une fois vérifiés fusionnés (tous fusionnés et propres, supprimés le 2026-09-14).
- [x] texsmith : 24 worktrees `.claude/worktrees/agent-*` et leurs branches
      `worktree-agent-*` supprimés une fois vérifiés fusionnés (idem, 27 branches).
- [x] texsmith : `build-migr/` et `scripts/migrate_examples.py` supprimés (4d5910b) ; les notes
      `specs/migration/*` restent comme archive référencée par le code ; `specs/README.md` mis à jour.
- [ ] tmark : `design/13-handoff.md` réécrit pour l'état post-merge.

## 6. Release tmark

- [ ] Nom PyPI décidé (`tmark` est pris par un autre projet) ; `pyproject.toml`,
      `module-name` et les imports texsmith alignés. **Décision utilisateur.**
- [ ] Version 0.1.0, `version =` sur chaque dépendance de chemin ou
      `publish = false` explicite ; premier tag `v0.1.0`.
- [ ] Job CI MSRV 1.80.
- [ ] Tests de `tmark-lint` étoffés (3 aujourd'hui pour 12 règles).
- [ ] `texsmith-migration` fusionnée dans `main`, CI verte sur GitHub.

## 7. Release texsmith

- [ ] `pyproject.toml` : `tmark>=0.1,<0.2` depuis PyPI, plus de
      `[tool.uv.sources]` path ; `vendor/tmark` retiré.
- [ ] Les six `ref: texsmith-migration` remplacés par le tag.
- [ ] CI verte sur GitHub (lint, pytest matrice, parity, examples).
- [ ] `CHANGELOG.md` : section 0.7.0 datée, pertes listées (entrée `.html`,
      API Python, plugins `texsmith.counters` / `texsmith.index` no-op).
- [ ] Pile `refactor/*` fusionnée dans `master`, tag `v0.7.0`.

## Reporté, hors périmètre du merge

- Découpage de `render` (722 lignes) et des fonctions de lowering > 300 lignes.
- Une seule source pour `texsmith.typ` (deux copies aujourd'hui).
- Zensical / MkDocs sans passage par le HTML : à concevoir contre ce que
  Zensical émet.
- Preview Typst dans le LSP (tmark M4).
