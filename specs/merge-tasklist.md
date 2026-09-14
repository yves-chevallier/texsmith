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

- [ ] **Échappement Typst** : `//` et `/*` cassés, `= + - /` en début de ligne
      et `~` échappés (`crates/tmark-writers/src/typst/escape.rs`), fixture de
      conformance, snapshots relus. Branche `fix/typst-escape`.
- [ ] **Sémantique des citations** : un `@key` nu rend la citation courte
      (`\cite` / `#cite(key)`) par défaut ; une clé de front matter bascule en
      narratif (`\textcite` / `form: "prose"`) ; `@[key]` reste parenthétique ;
      spec §Citations et `12-spec-challenges.md` mis à jour ; fixtures et
      snapshots. Branche `fix/citations`.
- [ ] Les deux branches fusionnées dans `texsmith-migration`, `cargo test`,
      `clippy -D warnings`, `fmt --check`, artefacts générés à jour.

## 2. Revue de la spec

- [ ] Revue de conformité indépendante spec ↔ code sur C27–C50
      (`design/reviews/07-spec-conformance-migration.md`), findings triés.
- [ ] Revue de cohérence interne de `spec/tmark.md` comme spécification de
      langage (`design/reviews/08-spec-consistency.md`), findings triés.
- [ ] Chaque finding classé : corrigé, reporté avec numéro de challenge, ou
      rejeté avec raison.

## 3. Correctifs texsmith

- [ ] Les 24 `warnings.warn` routés par `emit_diagnostic` avec un code, ou
      supprimés avec raison ; `--strict` et `--diagnostics-json` les voient.
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

- [ ] Compteurs personnalisés : `~/bien-air/review` (`counters: fw`,
      `#{fw:key}`, `@fw:key`) passe `tmark lint --fix` et se construit en PDF
      avec les mêmes numéros ; documenté dans `docs/syntax/counters.md`.
- [ ] Substitution de fontes XeLaTeX / passe `scripts` : un document CJK +
      grec + arabe se construit avec les mêmes `\tsscript` qu'en 0.6.0.
- [ ] Numérotation site-wide et index dans le plugin MkDocs unique, vérifiés
      sur `examples/mkdocs`.

## 5. Nettoyage des artefacts de migration

- [ ] tmark : 14 worktrees `~/tmark-wt/*` et leurs branches `wt/*` supprimés
      une fois vérifiés fusionnés.
- [ ] texsmith : 24 worktrees `.claude/worktrees/agent-*` et leurs branches
      `worktree-agent-*` supprimés une fois vérifiés fusionnés.
- [ ] texsmith : `build-migr/`, `scripts/migrate_examples.py` et les notes
      `specs/migration/*` archivées ou supprimées ; `specs/README.md` mis à jour.
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
