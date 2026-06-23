# Plan de migration — phases

Légende des critères de sortie : **GATE** = bloquant, doit être vert pour passer à la phase
suivante. Le GATE universel est `tools/snapshot.py diff == 0` (golden) + `uv run pytest` vert
+ `uv run ruff check .` + `uv run ruff format --check .`.

---

## Phase 0 — Filet de sécurité (golden harness)

**But.** Rendre la migration *vérifiable*. Capturer le `.tex` produit aujourd'hui pour chaque
exemple, snippet et page MkDocs, puis fournir un `diff` normalisé reproductible.

**Pourquoi en premier.** Les exemples font foi (cf. principes). Sans baseline figée, aucune
phase suivante n'est démontrable. C'est l'unique chose qui *prouve* l'iso-rendu.

**Périmètre / livrables.**
- `refactoring/tools/snapshot.py` : convertit en `.tex` (sans `--build`) :
  - tous les dossiers de `examples/Makefile` (`abbr, admonition, booby, book, code, colorful,
    diagrams, dialects, emoji, fonts, index, letter, marginnote, markdown, math, mermaid,
    multi-document, mkdocs, paper, progressbar, recipe, snippet`),
  - les snippets de `examples/snippet`,
  - le build MkDocs (`examples/mkdocs`, `examples/paper/mkdocs.yml`) via le plugin.
- **Normalisation** des champs volatils avant comparaison : dates (`\today`, `5 mars 2026`…),
  versions git (`v1.2.3-dirty`…), chemins absolus, hashes d'assets (`image-<sha>.pdf`),
  horodatages. Un même document non modifié doit donner un diff vide sur deux exécutions.
- `refactoring/baseline/<example>/…` : snapshots committés.
- Commandes : `python refactoring/tools/snapshot.py capture` (régénère baseline),
  `… diff` (compare HEAD au baseline, code retour ≠ 0 si écart).
- Documenter dans `tools/README.md` les sources de non-déterminisme connues et comment elles
  sont neutralisées.

**Hors-périmètre.** Toute modification de `src/`. Phase 0 est purement additive et outillage.

**Risques.** Diagrammes (mermaid/drawio) dépendent de Docker → marquer ces exemples
`requires-docker` et permettre `--skip-docker` ; ne pas faire échouer le filet si Docker absent,
mais signaler la couverture réduite. Polices (fonts) → assets téléchargés ; normaliser les noms.

**GATE de sortie.**
- `snapshot.py capture` puis `snapshot.py diff` → diff vide.
- `make -C examples all` (au moins en `--engine tectonic` sur les exemples non-Docker) passe.
- `tools/README.md` liste explicitement ce qui est couvert / ignoré.

---

## Phase 1 — Modèle IR

**But.** Définir la représentation intermédiaire typée. Aucun consommateur encore : pur ajout.

**Périmètre / livrables.**
- `src/texsmith/ir/nodes.py` : hiérarchie scellée `Block` / `Inline` (dataclasses `slots=True`,
  `frozen=True` quand possible). Esquisse de référence :

  ```python
  # Inline
  Str(text); Space(); SoftBreak(); LineBreak()
  Emph(content); Strong(content); Strikeout(content); Underline(content)
  Subscript(content); Superscript(content); SmallCaps(content)
  Code(text, lang="text"); Math(text, display=False)
  Link(content, target, title=""); Cite(keys: tuple[str,...], mode)
  Note(content)  # footnote
  # Block
  Para(content); Plain(content); Header(level, content, identifier="")
  CodeBlock(text, lang, highlight=(), lineno=False, filename=None)
  BlockQuote(content); BulletList(items); OrderedList(items, start, style)
  DefinitionList(items); HorizontalRule()
  Table(caption, columns: tuple[Column,...], head: tuple[Row,...], body: tuple[Row,...])
  Figure(content, caption, placement=None)
  # Column.alignment = Alignment.{LEFT,RIGHT,CENTER,JUSTIFY}  ← sémantique, pas "lrX"
  # Échappatoires & extensions
  RawInline(format, text); RawBlock(format, text)   # format ∈ {"latex","typst",...}
  Span(content, attrs); Div(content, attrs)         # générique à la pandoc
  # Nœuds d'extension first-class (au choix : typés OU Div/Span+attrs) :
  Admonition(kind, title, content); MarginNote(side, content)
  IndexEntry(path: tuple[str,...], style); ProgressBar(fraction); TexLogo(name)
  ```
- `src/texsmith/ir/visitor.py` : `NodeVisitor` (dispatch par type) + `walk`/`map` utilitaires.
- `src/texsmith/ir/__init__.py` : exports.
- Tests unitaires : construction, égalité, visitor, round-trip de structure.

**Décisions à arbitrer (Architect/IR Owner).**
- Nœuds d'extension **typés** vs **`Div/Span` générique + attributs**. Recommandation : typés
  pour les concepts stables et testés (Admonition, Table, MarginNote, IndexEntry, TexLogo,
  ProgressBar) ; `Div/Span` pour le reste, pour ne pas exploser le nombre de types.
- Où vit l'état transverse (acronymes, citations, compteurs, footnotes, index) : **dans le
  writer** (`WriterState`) et non dans l'IR. L'IR reste un arbre pur. (Migration la plus simple.)

**GATE de sortie.** Types + tests + pyright clean. Rien d'autre n'utilise l'IR (aucune
régression possible).

---

## Phase 2+3 — Le « Core swap » (HtmlReader + LaTeXWriter à parité)

> **Ces deux phases livrent ensemble** : tant que le writer LaTeX n'existe pas, remplacer le
> reader casse tout. Reader et Writer sont développés **en parallèle contre le contrat IR figé**
> (publié par l'Architect en fin de Phase 1), puis branchés d'un coup.

### Phase 2 — HtmlReader (HTML → IR)

**But.** Transformer l'arbre BeautifulSoup en IR, au lieu de le muter en LaTeX.

**Périmètre / livrables.**
- `src/texsmith/readers/html.py` (ou package `readers/html/` découpé par concern : blocks,
  inline, media, admonitions, code, links — miroir de l'actuel `adapters/handlers/`).
- Décorateur de lowering `@reads(tag, ...)` produisant un **nœud IR** (et non une mutation).
  Réutilise l'infrastructure topologique de `core/rules.py` (phases/priorités/before-after) si
  utile, mais le résultat est un arbre IR construit, pas un soup muté.
- Migration des `extensions/*/renderer.py` : la partie **HTML→sémantique** descend dans le
  reader (ex. `<ts-marginnote data-side>` → `MarginNote(side=…)` ; `data-ts-*` → `Table(...)`).
- **Suppression** progressive de `adapters/handlers/*` au fur et à mesure.

**Points durs.** `render_footnotes`, tables (réutiliser `extensions/tables/schema.py` qui est
*déjà* un modèle sémantique — le brancher directement sur `Table` IR supprime l'aller-retour
`data-ts-*`), math (détection inline/display), critic markup, snippets.

### Phase 3 — LaTeXWriter (IR → LaTeX) à parité

**But.** Produire le LaTeX actuel à partir de l'IR, **en réutilisant les partials Jinja et
`LaTeXFormatter` existants** (`adapters/latex/formatter.py`, `partials/*.tex`).

**Périmètre / livrables.**
- `src/texsmith/writers/latex/` : `LaTeXWriter` (visitor IR → str), `WriterState`
  (citations, acronymes, compteurs, footnotes, index, `requires_shell_escape`, `pygments_styles`),
  `escaper.py` (déplace `escape_latex_chars` ici, responsabilité du backend).
- Décorateur d'émission `@writes(NodeType)` pour le backend LaTeX (registre extensible).
- Migration de la partie **sémantique→LaTeX** des `extensions/*/renderer.py` vers des
  `@writes` du writer LaTeX.
- **Branchement du pipeline.** Dans `core/conversion/core.py`/`renderer.py`, remplacer
  `LaTeXRenderer.render()` (mutate+`get_text`) par
  `ir = HtmlReader().read(html); latex = LaTeXWriter(state).write(ir)`. Supprimer le chemin mort.
- **Bonus correctif.** Le scan de *font fallback* qui tourne aujourd'hui sur le LaTeX final
  ([renderer.py:371](../src/texsmith/core/conversion/renderer.py#L371)) opère désormais sur les
  `Str` de l'IR (backend-agnostique).
- Remplacer le dispatch magique `LaTeXFormatter.__getattr__`
  ([formatter.py:105](../src/texsmith/adapters/latex/formatter.py#L105)) par un dispatch typé
  `@writes` : erreur claire et localisée si un nœud n'a pas d'émetteur, plus d'`AttributeError`
  opaque, fin des `type: ignore[attr-defined]` afférents.

**GATE de sortie (le plus important du projet).**
- Golden `diff == 0` (après normalisation) sur **tous** les exemples non-Docker + Docker (si
  dispo) + snippets + MkDocs.
- `uv run pytest` vert. Tests de mécanique interne réécrits pour la nouvelle archi ; **aucun**
  test d'assertion sur le LaTeX produit relâché.
- `adapters/handlers/*` supprimé ; aucun `NavigableString(latex)` ni `soup.get_text()` résiduel
  comme mécanisme de rendu.
- Bilan net de fichiers : revue explicite qu'on n'a **pas** augmenté la surface (anciens
  handlers retirés).

---

## Phase 4 — TypstWriter (preuve du multi-backend)

**But.** Démontrer que l'IR autorise un second backend sans toucher au reader.

**Périmètre / livrables.**
- `src/texsmith/writers/typst/` : `TypstWriter` + `escaper.py` Typst + partials `.typ`.
- `@writes(NodeType)` pour le backend Typst sur un **sous-ensemble** d'abord (texte, titres,
  emphase, listes, code, math, liens, tables simples). Les nœuds non couverts lèvent une erreur
  **explicite et localisée** (« node MarginNote not supported by typst backend »).
- CLI : `--format {latex,typst}` (défaut `latex`). Moteur de build Typst optionnel.
- 1–2 exemples Typst (`examples/typst-hello`, `examples/typst-article`) + entrée golden dédiée.

**GATE de sortie.** Le sous-ensemble défini compile en `.typ` valide ; LaTeX golden toujours == 0
(le backend Typst n'a rien régressé côté LaTeX).

---

## Phase 5 — Nettoyage & resserrage

**But.** Encaisser la dette que la nouvelle archi rend supprimable. Faire baisser les métriques.

**Périmètre / livrables.**
- Supprimer `_FallbackConverter` (faux PDF placeholder,
  [core.py:730](../src/texsmith/core/conversion/core.py#L730)) → erreur explicite ou dépendance
  requise.
- Supprimer les shims top-level `progressbar.py`, `texlogos.py`, `index.py`, `quotes.py`,
  `smart_dashes.py` ; pointer les entry-points (`pyproject.toml`) vers `extensions/*`.
- Éradiquer les dernières conventions `data-ts-*` / classes LaTeX-aware encore présentes (tables
  d'abord, déjà entamé en Phase 2).
- Typer `context.runtime` (dataclass) ; supprimer le suivi par `id(node)` devenu inutile.
- Découper les god modules au besoin : `adapters/plugins/snippet.py` (1777 l.),
  `adapters/transformers/strategies.py` (1537 l.), `ui/cli/commands/render.py` (1169 l.).
- Resserrer les `except Exception` larges (~100) ; réduire les `Any` (~606) et `type: ignore`
  (~75) là où l'IR typée le permet.

**GATE de sortie.** Golden == 0, pytest vert, métriques de smell en baisse documentée dans
`PROGRESS.md`, revue « pas d'obscurcissement / pas d'inflation de fichiers ».

---

## Vue d'ensemble du séquençage

```
P0 (golden) ──► P1 (IR) ──► [P2 reader ∥ P3 writer LaTeX] ──► P4 (Typst) ──► P5 (cleanup)
   gate           gate              gate commun (parité)          gate          gate
```

P2 et P3 sont parallèles **mais** partagent un GATE unique (la parité golden). P4 et P5 peuvent
se chevaucher partiellement une fois la parité atteinte (P5 ne doit jamais casser le golden).
</content>
