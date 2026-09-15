# Merge tasklist — autoriser le merge tmark → main et texsmith → master

**Terminé le 2026-09-15** : tmark-core 0.1.0 et TeXSmith 0.7.0 sont publiés.
Ce fichier reste comme trace de ce qui a été vérifié avant la release.

Objectif : quand chaque case est cochée, le merge est autorisé et une release
peut être taguée. Une case n'est cochée qu'après vérification objective
(commande, test ou diff nommé). Mis à jour au fil du travail, dernière mise à
jour : 2026-09-15. État mesuré : tmark 340 tests, clippy, fmt, MSRV 1.80, artefacts propres ;
texsmith 1347 tests, ruff, parité 196 identiques / 0 différence, 49 tests des bindings.

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
- [x] Le sucre `++…++` avale « C++03 … C++ » en prose ; reconnaissance resserrée dans le tokenizer (01682b1, fixture `inline-keys-prose`, C61).

## 2. Revue de la spec

- [x] Revue de conformité indépendante spec ↔ code sur C27–C50
      (`design/reviews/07-spec-conformance-migration.md`) : 0 bloquant, 11 majeurs, 14 mineurs. Correction en cours sur `fix/spec-text` et `fix/spec-code`.
- [x] Revue de cohérence interne de `spec/tmark.md` comme spécification de
      langage (`design/reviews/08-spec-consistency.md`, 8e8dbce) : 5 bloquants, 15 majeurs, 19 mineurs.
- [x] Chaque finding classé : corrigé, reporté avec numéro de challenge, ou
      rejeté avec raison. Texte de la spec : fait (c3bf402, B1–B5, M1–M15, F3–F5, C52–C60).
      Code (F1, F2, F7, F8, F10, C27, C60, `strict-x-construct` supprimé) : fusionné (d8041cf).
      Régression de F2 sur le corpus (guillemet fermant devant `---`) corrigée (9029359, fixture `inline-quotes-dashes`).

## 3. Correctifs texsmith

- [x] Les 24 `warnings.warn` routés par `emit_diagnostic` avec un code, ou
      supprimés avec raison ; `--strict` et `--diagnostics-json` les voient.
      Fait (d6b2e0a) : 12 routés (`font-fallback`, `fragment-manifest`, `metadata-invalid`), 11 sur logger de module
      faute d'émetteur atteignable, 1 `UserWarning` gardé pour les auteurs de templates. 1345 tests.
- [x] Baseline de parité ré-enregistrée après le fix des citations, diff lu
      ligne par ligne (`scripts/parity.py baseline --check`). Fait (d3dbfb9) : 5 entrées, causes lues.
- [x] `docs/syntax/references.md`, `docs/guide/migration.md` et
      `CHANGELOG.md` décrivent la sémantique des citations et l'option. Fait (20efef0, 8bf7d89 : 2 tests prouvent `\cite` par défaut, `\textcite` sous la feature).
- [x] `DocumentState` purgé de ses champs et méthodes morts (f82be92 ; `_citation_index` était vivant, gardé).
- [x] `_LegacyContext` / `runtime[...]` de `passes/assets.py` remplacés par
      une signature typée depuis `PassContext`. Fait (3835aae, `AssetOptions`).
- [x] Cycle `passes` ↔ `core.conversion` cassé ; les imports locaux qui
      l'absorbaient remontés au niveau module. Fait (7d59acc, `core/options.py`) ; un cycle plus large via `snippet.py` reste documenté.
- [x] `unicodeblocks` retiré de `pyproject.toml` (déjà inutilisé en 0.6.0) ;
      `pyxindy` conservé (index via `adapters/latex/pyxindy.py`) ;
      `beautifulsoup4` et `pylatexenc` évalués. Fait (cff2ccc) : les deux gardés avec justification.
- [x] `wheel_schema_mismatch()` appelé au démarrage (tmark importé par le
      reader) et testé. Fait (953d46a).

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
- [x] tmark : `design/13-handoff.md` réécrit pour l'état post-merge (78e63dd).

## 6. Release tmark

- [x] Nom PyPI décidé : `tmark-core`, import `tmark` inchangé, dépôt GitHub renommé `tmark-core` (2026-09-14) ;
      `pyproject.toml` des deux dépôts et les `repository:` du CI alignés.
- [x] Version 0.1.0, `version =` sur chaque dépendance de chemin ou
      `publish = false` explicite (4bd0d0b, ebeff13) ; `Cargo.lock` repointé pour la MSRV (4f22f38). **Tag `v0.1.0` : pas encore posé.**
- [x] Job CI MSRV 1.80 (dad4f56) ; `cargo +1.80 check --workspace` passe localement.
- [x] Tests de `tmark-lint` étoffés (2 → 8 tests, une par règle, 5cf6551).
- [x] `texsmith-migration` fusionnée dans `main` (a3e218b, fast-forward, CI verte run 34936062610) ;
      tag `v0.1.0` posé sur 8e4b4e8. **`tmark-core` 0.1.0 publié sur PyPI** le 2026-09-15
      (4 roues abi3 + sdist), installation vérifiée dans un venv neuf. Trois défauts corrigés en route :
      le glob `dist/tmark-*.whl` (le fichier est `tmark_core-*.whl`), `maturin upload` déprécié remplacé par
      `pypa/gh-action-pypi-publish`, et le trusted publisher dont le champ *Workflow name* était vide.

## 7. Release texsmith

- [x] `pyproject.toml` : `tmark-core>=0.1,<0.2` depuis PyPI, plus de
      `[tool.uv.sources]` path ; `vendor/tmark` retiré (39a733f).
- [x] Les sept `ref: texsmith-migration` supprimés avec le checkout de tmark et l'installation de Rust :
      le CI installe la roue depuis PyPI (39a733f). Un test d'intégration qui atteignait le réseau est
      désormais sauté plutôt qu'en échec (c34cf28).
- [x] CI verte sur GitHub (lint, pytest matrice 9 jobs Linux/macOS/Windows, parity) : run 34841328180 sur le contenu
      de d65ac6f. Deux causes CI-only corrigées : usage box colorée (1dc4000), séparateurs Windows (3894e53, d65ac6f).
- [x] `CHANGELOG.md` : section 0.7.0 datée du 2026-09-15 (fd97856), pertes listées, plus les correctifs
      du 14 (citations, échappement Typst, keystrokes, guillemets, warnings vers le sink, chemins Windows).
- [x] Pile `refactor/*` fusionnée dans `master` (c34cf28, fast-forward), tag `v0.7.0` posé le 2026-09-15.

## Reporté, hors périmètre du merge

- Découpage de `render` (722 lignes) et des fonctions de lowering > 300 lignes.
- Une seule source pour `texsmith.typ` (deux copies aujourd'hui).
- Zensical / MkDocs sans passage par le HTML : à concevoir contre ce que
  Zensical émet.
- Preview Typst dans le LSP (tmark M4).
