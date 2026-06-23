# Suivi de migration — fichier vivant

> **Tout agent met à jour ce fichier en fin de tâche.** C'est le seul bus de communication
> inter-agents (état, blocages, verdicts de GATE, frictions de contrat IR).

## Tableau de bord des phases

| Phase | Agent | Statut | GATE | Notes |
|---|---|---|---|---|
| P0 — Golden harness | Golden Harness Engineer | 🟢 terminé | ✅ | 26 cas, diff vide reproductible (2×). Docker présent → diagrams/mermaid couverts ; skippés proprement si absent. |
| P1 — Modèle IR | Architect / IR Owner | 🟢 terminé | ✅ | `ir/{nodes,visitor,__init__}.py` + 26 tests verts. pyright 0 erreur, ruff clean, golden `diff --skip-docker` exit 0. Pur ajout, aucun consommateur. |
| P2 — HtmlReader | Reader Agent | 🟢 terminé | ✅ (commun P3) | `readers/html/` branché dans le live path. Golden `diff --skip-docker` exit 0. |
| P3 — LaTeXWriter (parité) | Writer Agent LaTeX | 🟢 terminé | ✅ (commun P2) | `writers/latex/` ; pipeline branché `read→write` ; golden `diff --skip-docker` **exit 0** (24/24 non-Docker, 2 skip Docker) ; `uv run pytest` = **798 passed** ; ruff + pyright(writers) clean. |
| P4 — TypstWriter | Writer Agent Typst | ⬜ à faire | ⬜ | — |
| P5 — Nettoyage | Cleanup Agent | 🟢 terminé | ✅ | `adapters/handlers/*` (11 fichiers) + `core/rules.py` + 3 shims top-level supprimés ; `__getattr__` magique retiré ; `_FallbackConverter` retiré ; entry-points repointés. Golden `diff --skip-docker` **exit 0**, `pytest` **795 passed**, ruff clean. Surface src P5 : **−12 fichiers / −4124 lignes**. `type: ignore` 89→**67**. |

Légende statut : ⬜ à faire · 🟡 en cours · 🟢 terminé · 🔴 bloqué
Légende GATE : ⬜ non franchi · ✅ franchi (GO Reviewer) · ❌ NO-GO

---

## Contrat IR figé  *(rempli par l'IR Owner en fin de P1)*

> Liste exhaustive des nœuds et de leurs champs. Reader et Writer consomment CECI.
> Aucune modification sans passer par « Frictions contrat IR » + arbitrage IR Owner.
>
> Source de vérité : `src/texsmith/ir/nodes.py`. Tous les nœuds sont des dataclasses
> `frozen=True, slots=True` ; les séquences d'enfants sont des **tuples** (hashables,
> égalité structurelle). Importer via `from texsmith import ir` puis `ir.<Node>`.

### Énumérations sémantiques

| Enum | Membres | Usage |
|---|---|---|
| `Alignment` | `LEFT, CENTER, RIGHT, JUSTIFY` | Alignement sémantique. `Alignment.from_short("l"\|"c"\|"r"\|"j")` fait le pont avec le modèle tables. **Jamais** `"r"`/`"lrX"` en IR. |
| `CitationMode` | `NORMAL, AUTHOR_IN_TEXT, SUPPRESS_AUTHOR` | Mode de rendu d'une `Cite`. |
| `ListStyle` | `DECIMAL, LOWER_ALPHA, UPPER_ALPHA, LOWER_ROMAN, UPPER_ROMAN` | Style de numérotation `OrderedList`. |
| `MarginSide` | `LEFT, RIGHT` | Marge d'une `MarginNote`. |

### Bases (scellées)

`Node` → racine. `Inline(Node)` et `Block(Node)` → marqueurs. `DefinitionItem(Node)` est un
nœud structurel (ni Block ni Inline) interne à `DefinitionList`. `Document(Block)` est la racine
conventionnelle. Union publique : `AnyNode = Block | Inline | DefinitionItem`.

### Nœuds Inline

| Nœud | Champs (type) | Sémantique |
|---|---|---|
| `Str` | `text: str` | Texte littéral (non échappé ; le writer échappe). |
| `Space` | — | Espace inter-mots. |
| `SoftBreak` | — | Saut de ligne source non significatif. |
| `LineBreak` | — | Saut de ligne dur (`<br>`). |
| `Emph` | `content: tuple[Inline,...]` | Emphase (`<em>`). |
| `Strong` | `content: tuple[Inline,...]` | Forte emphase (`<strong>`). |
| `Strikeout` | `content: tuple[Inline,...]` | Barré (`<del>`). |
| `Underline` | `content: tuple[Inline,...]` | Souligné (`<ins>`). |
| `Highlight` | `content: tuple[Inline,...]` | Surligné (`<mark>`). |
| `Subscript` | `content: tuple[Inline,...]` | Indice (`<sub>`). |
| `Superscript` | `content: tuple[Inline,...]` | Exposant (`<sup>`, ≠ footnote). |
| `SmallCaps` | `content: tuple[Inline,...]` | Petites capitales. |
| `Quoted` | `content: tuple[Inline,...]` | Citation inline (`<q>`) ; glyphes choisis par le writer. |
| `Code` | `text: str`, `lang: str=""` | Code inline (lang vide ⇒ monospace). |
| `Math` | `text: str`, `display: bool=False` | Math (source TeX brute) ; inline vs display. |
| `Link` | `content: tuple[Inline,...]`, `target: str`, `title: str=""` | Lien/réf. `target` = URL ou `#anchor`/label ; le writer choisit `\href` vs `\ref`. |
| `Cite` | `keys: tuple[str,...]`, `mode: CitationMode=NORMAL` | Citation biblio. |
| `Note` | `content: tuple[Block,...]` | Note de bas de page (corps porté inline, Pandoc-style). |
| `Image` | `src: str`, `alt: tuple[Inline,...]=()`, `title: str=""`, `width: str=""` | Image inline (une image légendée = `Figure` qui l'enveloppe). |
| `Span` | `content: tuple[Inline,...]`, `attrs: tuple[tuple[str,str],...]=()` | **Générique inline** : abbr/acronyme, `data-script`, liens unicode/regex, critic comment… `attrs` porte le hint sémantique (ex. `("role","abbr")`). |
| `RawInline` | `format: str`, `text: str` | Échappatoire backend inline (ignoré si `format` ≠ backend). |
| `IndexEntry` | `path: tuple[str,...]`, `style: str=""`, `registry: str=""`, `visible: tuple[Inline,...]=()` | Entrée d'index hiérarchique ; `style ∈ {"","b","i","bi"}`. |
| `TexLogo` | `name: str` | Logo nommé (`tex`/`latex`/`latex2e`). |
| `Keystroke` | `keys: tuple[str,...]` | Raccourci clavier (`("ctrl","s")`). |
| `MarginNote` | `content: tuple[Block,...]`, `side: MarginSide=RIGHT` | Note de marge. |

### Nœuds Block

| Nœud | Champs (type) | Sémantique |
|---|---|---|
| `Para` | `content: tuple[Inline,...]` | Paragraphe. |
| `Plain` | `content: tuple[Inline,...]` | Inline sans paragraphe (item de liste serrée). |
| `Header` | `level: int`, `content: tuple[Inline,...]`, `identifier: str=""`, `numbered: bool=True` | Titre de section (level 1..6). |
| `CodeBlock` | `text: str`, `lang: str=""`, `highlight: tuple[int,...]=()`, `lineno: bool=False`, `filename: str=""` | Bloc de code fencé (`highlight` = lignes 1-based). |
| `BlockQuote` | `content: tuple[Block,...]` | Citation bloc (`<blockquote>` simple ; les callouts sont des `Admonition`). |
| `BulletList` | `items: tuple[tuple[Block,...],...]` | Liste non ordonnée (chaque item = séquence de blocs). |
| `OrderedList` | `items: tuple[tuple[Block,...],...]`, `start: int=1`, `style: ListStyle=DECIMAL` | Liste ordonnée. |
| `DefinitionList` | `items: tuple[DefinitionItem,...]` | Liste de définitions (`<dl>`). |
| `DefinitionItem` | `term: tuple[Inline,...]`, `definitions: tuple[tuple[Block,...],...]` | Terme + définition(s). |
| `HorizontalRule` | — | Séparateur (`<hr>`). |
| `Table` | `model: tables.schema.Table`, `caption: tuple[Inline,...]=()`, `label: str=""`, `cells: tuple[tuple[Inline,...],...]=()`, `env: str=""`, `colspec: str=""`, `width: str=""`, `placement: str=""` | **Enveloppe le modèle (forme = SSOT)** + `cells` = contenu inline riche de chaque cellule (ordre HTML) + présentation pré-calculée des tables riches (`data-ts-*`). Voir note ci-dessous. |
| `Figure` | `content: tuple[Block,...]`, `caption: tuple[Inline,...]=()`, `identifier: str=""`, `placement: str=""` | Flottant légendé (image, table…). |
| `Admonition` | `kind: str`, `title: tuple[Inline,...]`, `content: tuple[Block,...]`, `collapsible: bool=False` | Callout (`kind` sémantique : note/warning/… ; `collapsible` ⇐ `<details>`). |
| `ProgressBar` | `fraction: float`, `label: tuple[Inline,...]=()`, `thin: bool=False` | Barre de progression (`fraction ∈ [0,1]`). |
| `Div` | `content: tuple[Block,...]`, `attrs: tuple[tuple[str,str],...]=()` | **Générique bloc** : lead-in, grid-cards, tabbed-set, multi-colonnes, groupes `data-script`… `attrs` porte le hint (ex. `("role","multicolumn"),("columns","2")`). |
| `RawBlock` | `format: str`, `text: str` | Échappatoire backend bloc. |
| `Document` | `content: tuple[Block,...]=()` | Racine du document (sous-type de `Block`). |

### Note `Table` (point d'attention Reader/Writer)

`Table.model` est une instance de `texsmith.extensions.tables.schema.Table` (Pydantic, déjà validée :
colonnes groupées récursives, `multirow`/`multicolumn`, séparateurs, alignement `l/c/r/j`, largeurs).
Choix délibéré : **ne pas dupliquer** ces ~870 lignes en dataclasses (SSOT/DRY). L'alignement y est la
forme courte à 1 lettre (sémantique, pas un préambule LaTeX) ; le writer utilise `Alignment.from_short`.
`caption`/`label` sont remontés au niveau IR pour porter du contenu inline + un identifiant.
Le `model` n'est **pas** traversé par `walk`/`map_tree`/`children` (ce n'est pas un `Node`) ; il ne porte
que la **forme** (spans, séparateurs, colonnes/groupes, alignement). Ses cellules restent **scalaires**
(`str|int|float|bool|None`) — **par conception** : on n'y range jamais d'arbre IR.

**Contenu inline riche des cellules — `cells` (ajout P2, friction #6 résolue).**
Le contenu *rendu* de chaque cellule (gras, code inline, liens, guillemets typographiques, spéciaux à
échapper `%`→`\%`, etc.) est porté **à part** dans `cells`, un tuple plat de runs inline dans **l'ordre
document du HTML** — exactement l'ordre où `render_table_html` émet les `<th>/<td>` (caption exclue) :
par ligne, d'abord toutes les cellules d'en-tête niveau par niveau (ordre `_header_matrix` : nom de groupe
avant ses sous-colonnes), puis pour chaque ligne body/footer la cellule-label suivie de ses cellules de
données à leur position d'origine (les slots absorbés multirow/multicolumn **absents**, comme dans le HTML) ;
les lignes séparateur ne contribuent **aucune** entrée (leur label éventuel reste scalaire dans
`Separator.label`). Chaque entrée est `tuple[Inline,...]` (vide pour une cellule blanche), prête pour le
chemin d'émission inline normal du writer (qui applique l'échappement `%`→`\%`, `\texttt{…\allowbreak{}…}`,
`\textbf{}`, etc. — **le reader ne pré-échappe pas**, il pose `Str("50%")`, `Code("mkdocs-material")`,
`Strong(...)`). **Les `cells` SONT des enfants** : le visitor les traverse (donc font-fallback / citations /
scan transverse atteignent aussi le contenu des cellules). Le writer parcourt `cells` **en lockstep** avec
les cellules qu'il itère déjà : chemin yaml = les `<th>/<td>` de `render_table_html(model)` (même ordre
document) ; chemin GFM nu = les colonnes-feuilles puis, par ligne, `[label, *DataRow.cells]` — **le même
ordre**, puisqu'une table nue n'a ni groupe, ni span, ni séparateur labellisé.

**Présentation des tables riches — `env`/`colspec`/`width`/`placement` (ajout P2, friction #5 résolue).**
Le pipeline legacy a DEUX chemins LaTeX de table : (1) GFM nu → partial `table.tex` (`tabularx`
`>{\raggedright\arraybackslash}X…`, en-tête gras, `\midrule`) ; (2) table `yaml`/`data-ts-table="1"`
→ partial `yaml_table.tex` (colspec custom, `tabular`/`tabularx`/`longtable`, `multirow`/`multicolumn`,
`\cmidrule(lr){a-b}`, séparateurs labellisés, cellules riches). Ces 4 champs portent la **directive de
mise en page pré-calculée** (`compute_layout`) des tables riches, recopiée *verbatim* depuis les attributs
`data-ts-*` du `<table>`. C'est une **échappatoire documentée et bornée** (le format propre de l'extension
tables, pas une chaîne backend générique) : les largeurs par colonne et les *wrappers* de préambule
(`>{\raggedright\arraybackslash}p{3cm}`) fondus dans le colspec **ne sont pas récupérables** à partir du
texte aplati des `<th>/<td>` ; les re-dériver par cellule casserait la parité bit-à-bit.

Contrat de branchement pour le Writer :

- `env == ""` → **table GFM nue** (pas de `data-ts-table`). Le writer rend via `table.tex` **uniquement à
  partir de `model`** ; alignements via `Alignment.from_short` sur `column_leaves(model.columns)`
  (`l/c/r/j` → `left/center/right`, `j`→`left` côté plain). Les 3 autres chaînes sont vides/inutilisées.
- `env != ""` → **table riche**. `env ∈ {tabular, tabularx, longtable}` → `\begin{tabularx}{<width>}{<colspec>}`
  / `\begin{longtable}{<colspec>}` / `\begin{tabular}{<colspec>}`. `width` = largeur externe (vide pour
  `tabular`), `placement` = spécif. flottant (peut être vide), `colspec` = préambule complet. Le writer
  **émet le préambule depuis ces chaînes** et **assemble header/body/footer depuis `model`** (groupes,
  spans multirow/multicolumn, séparateurs reconstruits depuis le HTML par le reader).

**API précise pour reproduire `render_yaml_table` bit-à-bit** (chemin retenu et déjà câblé côté Writer dans
`writers/latex/tables.py`) : `render_table_html(node.model)` régénère **le HTML `data-ts` canonique
identique** (thead/tbody/tfoot — vérifié par round-trip dans les tests), que l'on repasse à
`extensions.tables.renderer._render_header(thead, total_cols)` / `_render_section(tbody|tfoot, total_cols)`
avec `total_cols = _count_colspec_slots(node.colspec)`, puis `formatter.yaml_table(env=node.env or "tabular",
colspec=node.colspec, width=node.width or "", placement=node.placement or None, caption=…, label=node.label
or None, header=…, body=…, footer=…)`. Le header pose les `\cmidrule(lr){start+1-start+cols}` par groupe ;
les séparateurs deviennent `\midrule` (ou `\midrule[\heavyrulewidth]` si double) + `\addlinespace`
+ `\multicolumn{N}{l}{\textit{label}} \\` quand labellisés ; multirow → `\multirow{n}{*}{…}`,
multicolumn → `\multicolumn{c}{align}{…}`. Garantie : `compute_layout(node.model)` redonne exactement
`(env, colspec, width, placement)` portés par l'IR, donc le writer peut **faire confiance aux chaînes**
ou recalculer — les deux concordent **sauf** quand la largeur par-colonne / `long: true` ne survit pas au
round-trip HTML (raison d'être des chaînes portées : s'y fier, ne pas recalculer).

### Visitor / traversée (`ir/visitor.py`)

| API | Signature | Comportement |
|---|---|---|
| `NodeVisitor` | sous-classer, définir `visit_<ClassName>(node)` | Dispatch par type via MRO : un `visit_Block`/`visit_Inline` capte une famille entière ; sinon `generic_visit` (descend + retourne `None`). |
| `children(node)` | `Node -> tuple[Node,...]` | Enfants directs (ordre de déclaration ; aplatit les tuples imbriqués). |
| `walk(node)` | `Node -> Iterator[Node]` | Pré-ordre (nœud puis descendants). |
| `map_tree(node, fn)` | `(Node, Callable[[Node],Node]) -> Node` | Reconstruit bas-en-haut (`fn` voit les enfants déjà mappés) ; nœuds frozen → arbre neuf, sous-arbres inchangés réutilisés. |
| `iter_child_fields(node)` | `Node -> Iterator[(str, value)]` | Champs porteurs d'enfants (introspection dataclass). |

Découverte d'enfants **structurelle** : tout champ contenant un `Node` (ou un tuple, même imbriqué,
de `Node`) est un slot enfant ; les champs scalaires et le `model` de `Table` sont ignorés. ⇒ un
nouveau type de nœud ne nécessite aucune modif du visitor s'il range ses enfants en champs node/tuple.

### Cartographie de l'état transverse (→ `WriterState`, Phase 3, PAS dans l'IR)

| `DocumentState` (champ) | Dérivé de (nœud IR) | Destination `WriterState` |
|---|---|---|
| `citations` / `_citation_index` | `Cite.keys` | registre de citations (ordonné) |
| `bibliography` | front matter / reader | base bibliographique |
| `abbreviations`/`acronyms`/`acronym_keys`/`glossary`/`acronym_*groups` | front matter / reader + `Span` role=abbr | registre glossaire |
| `footnotes` | `Note.content` | registre de footnotes |
| `index_entries` / `has_index_entries` | `IndexEntry` | registre d'index |
| `counters` / `exercise_counter` | (interne writer) | table de compteurs |
| `requires_shell_escape` | engine de `Code`/`CodeBlock` | flag shell-escape |
| `pygments_styles` | `CodeBlock.lang` | registre de styles |
| `fallback_summary` | scan de `Str.text` | rapport font-fallback (déplacé sur l'IR, cf. PLAN P3) |
| `headings` | `Header` | constructeur de TOC |
| `script_usage` | attr `script` de `Span`/`Div` | tracker `data-script` |
| `callouts_used` | `Admonition` | flag callouts |
| `snippets` / `solutions` | reader (pré-IR) | résolus en amont, hors WriterState |

---

## Frictions contrat IR  *(Reader / Writer écrivent ici ; IR Owner arbitre)*

### Reader (P2) — frictions rencontrées (signalées, NON corrigées dans l'IR)

1. **Cellules de table scalaires (RÉSOLU → voir friction #6).** Le `model` reste
   scalaire pour la *forme*, mais le contenu inline riche est désormais porté par
   `Table.cells`. ~~L'inline riche dans une cellule était aplati en texte.~~ Le reader
   lowerise chaque `<td>`/`<th>` via `ctx.lower_inline`. Friction close.
2. **Tables < 2 colonnes non représentables.** `schema.Table` impose `min_length=2`
   colonnes. Une table HTML à une seule colonne (rare mais présente : 3 cas dans le
   golden) ne peut pas être modélisée → repli explicite en `Div` role=`table-fallback`
   + warning. Pas une demande de changement IR : repli volontaire et lossless.
3. **Concepts sans nœud typé → `Span`/`Div` + `role` (conforme, pas une friction).**
   Le reader encode via `attrs` `role=…` : `abbr` (+`title`), `critic-deletion`/
   `critic-addition`/`critic-highlight`/`critic-comment`/`critic-substitution`,
   `script` (+`script=slug`), `regex` (+`href`), `label` (+`id`), `footnote-ref`
   (+`ref`), `emoji`, `task-marker` (+`checked`), `multicolumn` (+`columns`),
   `epigraph`, `tabbed-set`/`tab` (+`title`), `footnotes`, `table-fallback`.
   **Le Writer P3 doit connaître ce vocabulaire de `role`** (voir rapport ci-dessous).
   Aucun ajout de nœud IR demandé.
4. **Liens internes non résolus dans le reader.** L'ancien `links.py` résolvait des
   cibles fichier→`\ref` et enregistrait des snippets (I/O, état). Le reader pose un
   `Link(target=href)` brut (URL ou `#ancre`) **sans** résolution filesystem ni
   accès `state` (concerne le Writer/amont). Conforme au contrat (`target` = URL ou
   `#anchor`/label, writer choisit `\href`/`\ref`). Signalé pour que le Writer
   sache que la résolution fichier→ref n'a PAS été faite côté reader.
5. **Tables riches dégradées par le reader (RÉEL — corrigé, arbitré par l'IR Owner).**
   *Constat (Writer).* L'ancien `read_table` re-dérivait un `schema.Table` *positionnel
   plat* depuis le texte des `<th>/<td>`, jetant pour les tables `data-ts-table="1"` :
   `colspec`/`env`/`width`/`placement`, largeurs de colonnes, spans `multirow`/`multicolumn`,
   richesse des séparateurs, groupes de colonnes. ⇒ `recipe`/`paper`/`book` impossibles à
   reproduire bit-à-bit. *Décision IR Owner (option a).* `ir.Table` gagne 4 champs optionnels
   `env`/`colspec`/`width`/`placement` (échappatoire **bornée** : format propre de l'extension
   tables, pas une chaîne backend ; cf. note `Table` ci-dessus) recopiés *verbatim* depuis
   les `data-ts-*` ; ET le reader **reconstruit le modèle riche complet** (`_build_rich_table_model` :
   groupes via les niveaux de `<thead>`, `RichCell` pour `colspan`/`rowspan`/`data-ts-align`,
   `Separator` avec `label`/`double-rule`, report de multirow). Vérifié : `render_table_html(model)`
   régénère un thead/tbody/tfoot **identique** au HTML d'origine, et `compute_layout(model)`
   redonne les 4 chaînes portées. Le chemin GFM nu reste inchangé (4 champs vides → `table.tex`).
   **SSOT préservée** : `model` reste le `schema.Table` validé, non une re-dérivation dégradée.
   *Friction close.*
6. **Contenu de cellule = inline riche, pas texte scalaire (RÉEL — corrigé, arbitré par l'IR Owner).**
   *Constat (Writer).* Le renderer legacy tournait en POST *après* les handlers inline : `cell.get_text()`
   renvoyait du LaTeX déjà rendu (`\textbf{…}` ⇐ `**x**`, `\texttt{mkdocs-\allowbreak{}material}` ⇐ code
   inline, guillemets typographiques, spéciaux échappés `%`→`\%`). Le reader aplatissait `<td><strong>…`
   en `"…"` scalaire ⇒ le golden `markdown` (`\textbf{MultiMarkdown} & … & \texttt{multimarkdown}`)
   irreproductible côté writer. *Décision IR Owner.* Nouveau champ `ir.Table.cells:
   tuple[tuple[Inline,...],...]` : contenu inline rendu de chaque cellule, **ordre document HTML** (cf. note
   `Table`). `model` garde la forme scalaire (SSOT), `cells` porte le contenu. Le reader lowerise via
   `ctx.lower_inline(cell.children)` (en-têtes inclus) ; **pas de pré-échappement** (le writer échappe).
   `cells` sont de vrais enfants (traversés par le visitor). Vérifié : alignement 1-à-1 avec l'ordre du
   writer pour les DEUX chemins (yaml = `render_table_html(model)` ; GFM = colonnes puis `[label,*cells]`).
   *Friction close. Dernier gros bloqueur table levé.*

### Writer (P3) — frictions rencontrées (résolues côté reader/writer, AUCUN changement IR demandé)

Pour la parité bit-à-bit, plusieurs détails que l'ancien `get_text()` préservait
ont dû être restitués **sans toucher au contrat IR** (corrections reader/writer
fidèles aux anciens handlers) :

1. **Fidélité des blancs.** L'ancien `get_text()` gardait les blancs source
   verbatim. Le reader collapsait tout en `Space`. Corrigé côté reader : un run de
   blancs contenant un `\n` (soft-wrap Markdown + indentation de continuation) ou
   `>1` espace est conservé littéralement dans un `Str` ; un espace simple →
   `Space`. (Pas de changement IR : `SoftBreak` reste un marqueur sans payload, le
   littéral voyage dans `Str`.)
2. **Math littéral en texte.** `$…$` / `\(…\)` tapés en texte (non captés par
   mdx_math) étaient éclatés par la tokenisation. Corrigé : le reader détecte les
   payloads math et les pose en `RawInline(format="latex")` (verbatim), comme le
   faisait `escape_plain_text`.
3. **Joint inter-blocs.** Reproduit le modèle legacy (HTML : un seul `\n` entre
   tags de bloc ; chaque émetteur porte ses propres `\n` de bord) — joint writer à
   `\n`, pas `\n\n`.

Aucune de ces frictions n'a nécessité de modification de l'IR : ce sont des
responsabilités reader (normalisation) / writer (assemblage), conformes au contrat.

---

## Journal des GATES  *(Golden Harness / Reviewer)*

### P5 — Nettoyage & resserrage — 2026-06-23 — ✅ FRANCHI

- **GATE atteint** : `uv run python refactoring/tools/snapshot.py diff --skip-docker`
  = **exit 0** (24 capturés / 2 skip Docker / 0 fail) ; `uv run pytest` = **795 passed**
  (798→795 : suppression de `test_rule_ordering.py` qui testait le `RenderRegistry` mort) ;
  `ruff format --check` + `ruff check` verts ; pyright **0 erreur** sur `src/texsmith/writers`,
  `src/texsmith/readers`, `core/context.py`, `adapters/html_utils.py`. Les erreurs pyright
  résiduelles (snippet.py, fonts/scripts.py, core/conversion/core.py) sont **pré-existantes**
  (vérifié contre HEAD) et hors périmètre (variance de dict, "possibly unbound" legacy).

- **Dispatch mort supprimé** : `core/rules.py` (RenderEngine, `@renders`, RenderPhase,
  `_DOMVisitor`, RenderRegistry, RuleDefinition, RuleFactory, RenderRule) **supprimé** ;
  TOUS les `@renders` du code (handlers + extensions + plugins) retirés ; `RenderPhase`/`renders`
  retirés de `texsmith/__init__.py`. `core/context.py` : suivi de nœuds par `id(node)`
  (`phase`/`_processed_nodes`/`_skip_children`/`enter_phase`/`mark_processed`/`is_processed`/
  `suppress_children`/`should_skip_children`) supprimé — `RenderContext` réduit à la surface
  duck-typée que le writer lit (`config`/`formatter`/`document`/`assets`/`state`/`runtime`).

- **`adapters/handlers/*` supprimé entièrement** (11 fichiers, ~3000 l.). Helpers vivants relogés
  (ancien emplacement disparu, zéro ré-export de compat) :
  - `coerce_attribute`/`gather_classes`/`is_valid_url`/`resolve_asset_path` → **`adapters/html_utils.py`**
    (foyer partagé BS4). `mark_processed` supprimé (mort avec le moteur).
  - `_mermaid.py` (heuristiques mermaid) → **`adapters/transformers/mermaid_detect.py`**.
  - `_assets.py` (stockage d'images) → **`writers/latex/assets.py`** (writer-only).
  - helpers writer-only de `media`/`links`/`blocks` → **`writers/latex/{media,links,doi}.py`**.
  - `adapters/plugins/material.py` supprimé (100 % `@renders` mort ; exercises/epigraph passent
    par le writer IR). `extensions/{texlogos,marginnote}/renderer.py` supprimés (entièrement morts) ;
    `extensions/{progressbar,index,tables}/renderer.py` réduits à leurs exports vivants
    (`_compose_latex`, `INDEX_TEMPLATE`, `render_table_html`/`_render_header`/`_render_section`/…).

- **Shims top-level supprimés** : `index.py`, `texlogos.py`, `progressbar.py` (ré-exports minces)
  supprimés ; `quotes.py`/`smart_dashes.py` (vraie implémentation, pas des shims) déplacés vers
  **`extensions/quotes.py`** / **`extensions/smart_dashes.py`**. Entry-points `pyproject.toml`
  repointés vers `texsmith.extensions.*` ; groupe **`texsmith.renderers` (mort) supprimé** ;
  `DEFAULT_MARKDOWN_EXTENSIONS`, `extensions/__init__.py` (registre + `register_all_renderers`
  + `renderer_entry`/`iter_entry_points` morts retirés), `mkdocs_plugin.py`, `core/templates/wrapper.py`,
  docs (`api/handlers.md` réécrit pour `@reads`/`@writes`, `api/core.md`, `guide/extensions.md`,
  `custom-transformers.md`) repointés. Tests des shims/`register_renderer` (no-op) corrigés.

- **`_FallbackConverter` (faux PDF placeholder) supprimé** : il n'était jamais installé
  (`fetch-image` a toujours un vrai `FetchImageStrategy`), donc `ensure_fallback_converters` +
  `attempt_transformer_fallback` + la boucle de retry de `render_with_fallback` + le flag CLI
  `--no-fallback-converters` (config morte) ont été retirés. (Le placeholder PDF de
  `writers/latex/assets.py` pour échec de conversion SVG/drawio est une dégradation gracieuse
  documentée du convertisseur, conservé.)

- **`LaTeXFormatter.__getattr__`/`__getitem__` magiques supprimés** : remplacés par l'accès
  explicite `render_template(name, ...)` (déjà présent, route `handle_X` sinon partial). Tous
  les appels `formatter.<nom>()` (writer : `ref`/`href`/`deletion`/`addition`/`highlight`/
  `comment`/`label`/`horizontal_rule`/`codeinline*`/`handle_codeblock`/`handle_regex` ; snippet
  `_render_figure` `getattr(formatter, name)` ; mkdocs plugin `heading`) convertis en
  `render_template`. Méthodes mortes `url`/`svg`/`get_cover` supprimées (drop de plusieurs
  `type: ignore[attr-defined]`) ; assignations mortes `formatter.config`/`formatter.output_path`
  supprimées. (Le retrait du proxy a révélé 2 sites magiques cachés — snippet figure + mkdocs
  heading — désormais explicites ; le golden l'a prouvé.)

- **Dette de typage** : un Protocol `RenderContextLike` (`core/context.py`) capture la surface
  duck-typée commune à `RenderContext` et `WriterState` ; `fonts/scripts.py`, `writers/latex/
  {assets,media,links,doi}.py` et `adapters/plugins/snippet.py` l'utilisent → **9 `type: ignore
  [arg-type]` du `_fake_context` supprimés** (méthode `_fake_context` retirée). `type: ignore`
  **89→67** (≤ 75 ✓, et < base pré-migration 75). `Any` (mesure mot-entier) 739→735 ; la
  réduction agressive supplémentaire toucherait des modules config/template/YAML où `Any` est
  légitime (pas de découpage/typage risqué pour le chiffre, cf. garde-fou).

- **Bilan net de surface (P5, working tree avant→après)** : **184→172 fichiers `.py` (−12)**,
  **43 362→39 238 lignes (−4 124)**. La surface BAISSE.

- **Conservé, justifié** : `RenderContext` (live : `fonts/scripts.py`, duck-typé par le writer) ;
  `texsmith/plugins/__init__.py` (réexport `snippet` pour mkdocstrings — repointé, plus de
  `material`) ; les god modules `snippet.py` (1739), `strategies.py` (1537), `writer.py` (1428,
  issu de P3), `render.py` (1165) NON découpés (aucun découpage évident sans risque ;
  `except Exception` ~101 laissé tel quel — opportuniste, jugé risqué de resserrer sans cas).

### P2 + P3 — Core swap (HtmlReader + LaTeXWriter à parité) — 2026-06-23 — ✅ FRANCHI

- **GATE atteint** : `uv run python refactoring/tools/snapshot.py diff --skip-docker`
  = **exit 0** (24 cas capturés, 2 skip Docker `diagrams`/`mermaid`, 0 fail) ;
  `uv run pytest` = **798 passed, 0 failed** ; `ruff format --check` + `ruff check`
  verts ; pyright **0 erreur** sur `src/texsmith/writers`. (Docker absent dans
  l'env de validation → cas `diagrams`/`mermaid` non re-vérifiés ici, comme P0/P1/P2.)
- **Pipeline branché** : `adapters/latex/renderer.py` `LaTeXRenderer.render()` ne
  mute plus le soup ; il fait `ir = HtmlReader(...).read(html)` puis
  `LaTeXWriter(WriterState(...)).write(ir)`. Plus aucun `soup.get_text()` ni
  `NavigableString(latex)` comme **mécanisme de rendu** dans le live path ; plus
  d'`engine`/`@renders` dans le chemin live (le `core/conversion` factory + retry +
  copy_document_state restent inchangés).
- **Livré `writers/latex/`** :
  - `writer.py` — `LaTeXWriter` (visitor IR→str), un émetteur `@writes(NodeType)`
    par nœud IR ; dispatch typé par MRO. Reproduit la logique de TOUS les anciens
    handlers + plugins (basic/inline/blocks/code/links/media/admonitions, material
    exercises/epigraph, snippet, marginnote/progressbar/index/texlogos/tables).
  - `registry.py` — décorateur `@writes` + `WriterRegistry` (collecte par MRO, une
    instance par classe concrète → extensible par sous-classe). Un nœud sans
    émetteur lève `LaTeXWriteError` (type de nœud + backend) — fini l'`AttributeError`
    opaque (c'était l'objectif du remplacement du dispatch magique).
  - `state.py` — `WriterState` : enveloppe `DocumentState` + runtime + config +
    formatter + assets ; duck-type-compatible avec `RenderContext` pour réutiliser
    `fonts.scripts.render_moving_text` et les helpers d'assets verbatim.
  - `escaper.py` — déplace `escape_latex_chars` ici (responsabilité backend) + les
    transforms unicode (tirets, guillemets, sub/superscripts, segmentation emoji,
    protection des payloads math) qu'appliquait l'ancien `escape_plain_text` PRE.
  - `tables.py` — deux chemins (GFM plain → `table.tex` ; yaml/`data-ts` →
    `yaml_table.tex` via `render_table_html` + l'assembleur existant), contenu de
    cellule injecté depuis `Table.cells` (inline IR).
- **`__getattr__` magique** : le dispatch *nœud→émetteur* est désormais le registre
  typé `@writes`. Le `LaTeXFormatter.__getattr__` subsiste comme **proxy de
  *templates*** (résolution nom-de-partial→callable, consommé par les émetteurs et
  les helpers figure/diagram partagés) ; il lève maintenant un `TemplateNotFoundError`
  clair (nom + backend), jamais d'`AttributeError` opaque. Une méthode publique
  explicite `formatter.render_template(name, **kwargs)` a été ajoutée et les
  émetteurs l'utilisent. (Suppression complète du proxy = chantier P5, requiert de
  reloger les helpers de `handlers/*` que reader/writer réutilisent encore.)
- **Correctifs reader (parité, ports fidèles de `discard_unwanted`/handlers)** :
  préservation des soft-breaks + indentation de continuation + espaces multiples
  (verbatim, comme `get_text`) ; protection des payloads math `$…$`/`\(…\)` dans le
  texte ; strip des ancres chrome (`headerlink`/`footnote-ref`/`footnote-backref`) ;
  footnote-defs id-taggés ; `data-tag-name` index inline ; latex-raw inline ;
  twemoji span ; tabbed labels/blocks fallback ; mermaid par classe/contenu/`data-
  mermaid-source` ; epigraph footer ; exercise/snippet préservés en HTML verbatim ;
  `[ ]`/`[x]` tasklist textuel ; dl vide droppé.
- **Tests réécrits (mécanique interne / fragments d'anciens handlers)** :
  `test_renderer_entry_points.py` supprimé (engine entry-points retiré) ;
  `test_renderer_parser_fallback` conservé (fallback parser reporté dans le
  renderer) ; `test_strip_tags` : règle custom `strip_tags` (feature runtime
  retirée) remplacée par le test `latex-ignore` ; `test_counter_extension` :
  l'exemple `examples/custom-render/counter.py` **migré** vers le modèle
  `@reads`+`@writes` (sous-classe `CountingWriter`) ; `test_formatting`
  (strong/arithmatex/index-style) ajustés à la sortie canonique du pipeline
  document (le golden reste l'oracle). **Aucun** test d'assertion LaTeX sur un
  document réel relâché — le golden prouve la parité octet-à-octet.
- **Frictions IR résolues par l'IR Owner pendant le swap** (voir section dédiée) :
  yaml-tables (`env/colspec/width/placement` + reconstruction du modèle riche) et
  contenu de cellule inline (`Table.cells`).
- **Bilan fichiers** : `writers/` ajouté (`writers/__init__.py` + `writers/latex/`
  6 fichiers). Les `@renders` du dispatch live sont morts (plus d'engine), mais
  `adapters/handlers/*` (11 fichiers) **restent** car reader+writer réutilisent
  leurs *fonctions helper* (`_assets`, `media._render_mermaid_diagram`,
  `links._resolve_local_target`/`_infer_heading_reference`, `blocks._ensure_doi_*`,
  `_mermaid`, `_helpers`). La suppression nette des handlers + relogement des
  helpers = chantier P5 (la surface ne baisse donc pas encore ; le mécanisme de
  rendu, lui, est entièrement remplacé).

### P2 — HtmlReader — 2026-06-23 — 🟢 PRÊT (GATE commun avec P3)

- **Livré** : package `src/texsmith/readers/html/` (pur ajout, aucun branchement
  dans `core/conversion/`) :
  - `registry.py` — décorateur `@reads(*tags, level, priority, name)` + `ReaderRegistry`
    (miroir de `core.rules.renders`), sentinelle `NotHandled` (un lowering décline →
    le reader essaie le candidat suivant, sinon repli). `ReadLevel.{BLOCK,INLINE,ANY}`.
  - `context.py` — `ReadContext` : émetteur de diagnostics + callbacks récursifs
    `lower_inline`/`lower_blocks` (évite le cycle d'import reader↔handlers).
  - `reader.py` — `HtmlReader.read(html: str) -> ir.Document` (+ `read_tree(Tag)`).
    Double passe BLOCK/INLINE partageant le registre ; texte → `Str`/`Space` ;
    inline lâche entre blocs replié en `Para` ; **stripping** des `Space` de bord.
  - `inline.py`, `blocks.py`, `extensions.py` — lowerings (voir couverture).
  - `_helpers.py` — `coerce_attr`/`classes`/`attrs_tuple` (local à `readers/`, zéro
    dépendance vers `adapters/handlers/`).
- **Couverture handlers (`adapters/handlers/*`)** : basic (hr, br, em/strong/del/ins/
  mark/sub/sup/q, smallcaps, headings, grid-cards), inline (inline-code, math
  inline/block/script, abbr, keystrokes, script-spans, latex-text, twemoji,
  index, critic del/ins/mark/comment/subst, unicode/regex links), blocks
  (paragraphes, listes ord/non-ord + tasklist, dl, blockquote, latex-raw,
  multicolonnes, figures, tables, footnote-refs/missing-footnote), code
  (pre, div.highlight + filename/lineno/hll, mermaid→CodeBlock), links
  (a, autoref, autoref-spans), media (img, figure).
- **Couverture extensions (`extensions/*/renderer.py`, partie HTML→sémantique)** :
  marginnote (`<ts-marginnote data-side>` → `MarginNote`), progressbar
  (`div.progress` → `ProgressBar`), index (`span.ts-hashtag` `data-tag*` →
  `IndexEntry`), texlogos (`span.tex-logo` → `TexLogo`), tables
  (`<table>` yaml `data-ts-*` **ou** GFM → `Table` enveloppant `schema.Table`,
  via `parse`/`LeafColumn`/`DataRow` — supprime l'aller-retour `data-ts-*`),
  admonitions/material (`div.admonition`, `<details>`, `> [!TYPE]` → `Admonition`).
- **Stratégie de repli (rien d'avalé en silence)** : tag sans lowering → warning
  via l'émetteur de diagnostics **+** nœud générique `Div` (bloc) / `Span` (inline)
  conservant `html-tag` + `class` d'origine et les enfants lowerés. Vérifié par
  sweep sur **tous** les `examples/**/*.md` (markdown→html→IR) : 0 crash ; seuls
  replis = 3 tables 1-colonne (warning explicite + `Div` lossless). `features.md`
  (628 l., éventail complet) → 0 repli.
- **Tests** : `tests/test_html_reader.py` — 44 tests : un cas par type de nœud /
  handler (texte/espaces, emphase, code inline/bloc, headings, listes serrées→`Plain`
  + tasklist, dl, blockquote + callout `[!TYPE]`, liens/autoref, math inline/bloc/
  script, image/figure, admonition/details, marginnote, progressbar, index, texlogo,
  keystroke, abbr, critic, tables→schema + caption/label + repli 1-colonne),
  robustesse (repli bloc/inline + warning), extensibilité du registre `@reads`,
  et **intégration markdown→html→IR sans perte silencieuse**.
- **GATE** : `ruff check .` + `ruff format --check` verts ; pyright **0 erreur**
  sur `src/texsmith/readers` ; `uv run pytest` = **789 passed** (745 + 44) ;
  golden `snapshot.py diff --skip-docker` = **exit 0** (24 capturés / 2 skip Docker /
  0 fail). **Pur ajout** : aucune modif de `adapters/handlers/*`, des
  `extensions/*/renderer.py`, ni de `core/conversion/` → chemin live intact.
  GATE final commun avec P3 (parité golden) : à franchir quand le Writer branche
  `read+write`.

### P1 — Modèle IR — 2026-06-23 — ✅ FRANCHI

- **Livré** : `src/texsmith/ir/nodes.py` (hiérarchie scellée `Block`/`Inline`,
  dataclasses `frozen=True, slots=True`, enfants en tuples), `ir/visitor.py`
  (`NodeVisitor` + `walk`/`map_tree`/`children`/`iter_child_fields`),
  `ir/__init__.py` (exports), `tests/test_ir_nodes.py` + `tests/test_ir_visitor.py`
  (26 tests : construction, defaults, égalité structurelle, hashing, immutabilité,
  `Alignment.from_short`, wrapping du modèle table, escape hatches, visitor MRO,
  walk pré-ordre, map_tree bottom-up/pure).
- **Arbitrages typé vs générique** : typés = Admonition, Table (wrap du modèle
  `extensions.tables.schema.Table`), MarginNote, IndexEntry, TexLogo, ProgressBar,
  Keystroke, Note, Cite, Math, Image, Figure (+ tous les inlines/blocs de base).
  Génériques `Span`/`Div`+attrs = lead-in, grid-cards, tabbed, multi-colonnes,
  `data-script`, liens unicode/regex, critic comment.
- **SSOT table** : `Table` enveloppe le modèle Pydantic existant (pas de duplication).
  Limite documentée : cellules scalaires, pas d'inline riche dans les cellules.
- **GATE** : pyright `0 errors, 0 warnings` sur `src/texsmith/ir` ; `ruff check .`
  + `ruff format --check .` verts ; `uv run pytest` = **745 passed** ; golden
  `snapshot.py diff --skip-docker` = **exit 0** (24 capturés / 2 skip Docker / 0 fail).
  Pur ajout : aucun consommateur de l'IR dans `src/`, donc aucune régression possible.
- **Contrat IR figé** rempli ci-dessus → consommable par Reader (P2) et Writer (P3).

### P0 — Golden harness — 2026-06-23 — ✅ FRANCHI

- **Outillage livré** : `refactoring/tools/snapshot.py` (`capture` / `diff` /
  `list`, options `--only` et `--skip-docker`) + `refactoring/tools/README.md`.
  Baseline figée sous `refactoring/baseline/` (26 cas, 76 fichiers `.tex`/`.sty`,
  ~768 KiB).
- **Couverture (26 cas)** : tous les dossiers de `examples/Makefile` dérivés 1:1
  des Makefiles, sans `--build`/`--engine` (pas de PDF). `code` → 2 cas
  (block/inline) ; `emoji` → 2 cas (default/bw) ; `letter` → 3 (din/sn/nf) ;
  `mkdocs` via `mkdocs build` (sans `TEXSMITH_BUILD`) → `press/**`.
- **Cas Docker** : `diagrams` et `mermaid` marqués `requires-docker`. Docker
  présent dans l'environnement de capture → couverts. Sans Docker (ou
  `--skip-docker`) → **skippés, pas en échec** (24 capturés / 2 skippés / exit 0).
- **Déterminisme vérifié** : `capture` puis `diff` × 2 consécutifs → diff vide,
  exit 0 les deux fois. Normalisation des champs volatils (dates `\today` /
  long-form FR+EN, timestamps ISO, versions git, hashes d'assets `<nom>-<sha>`
  et `<sha64>`, chemins absolus) — liste de regex documentée dans `snapshot.py`
  et `tools/README.md`.
- **Hors périmètre / limites** : PDF non snapshotés (non déterministes) ;
  `examples/paper/mkdocs.yml` ne câble PAS le plugin texsmith (site Material nu,
  0 `.tex`) → contenu `paper` couvert via le cas CLI `paper` (cheese.md).
- **Lint** : `uv run ruff check .` et `ruff format --check` verts. Ajout d'un
  `per-file-ignores` pour `refactoring/tools/**` (script CLI : `print` =
  canal de sortie). Aucune modification de `src/`.

---

## Métriques de référence (avant migration)

À faire baisser en P5, mesuré à nouveau en fin de projet :

| Métrique | Avant | Après |
|---|---|---|
| `type: ignore` (src) | 75 (base) ; 89 (post-P3) | **67** (≤ 75 ✓ ; sous la base pré-migration) |
| annotations `Any` (mot-entier, src) | 739 (HEAD) | **735** (les `Any` restants vivent surtout en modules config/template/YAML, légitimes ; pas de typage risqué pour le chiffre) |
| `except Exception` larges | 100 | **101** (inchangé — opportuniste ; resserrage jugé risqué sans cas précis) |
| occurrences `TODO/legacy/deprecated/backward` | 109 | **145** (bruit : surtout `legacy_latex_accents` (option de config) + docstrings décrivant l'ancien pipeline ; pas de la dette `TODO` réelle ajoutée) |
| handlers `adapters/handlers/*.py` | 9 fichiers (puis 11 post-P3) | **0** — package **supprimé** ; helpers vivants relogés (`adapters/html_utils.py`, `adapters/transformers/mermaid_detect.py`, `writers/latex/{assets,media,links,doi}.py`) |
| `core/rules.py` (moteur `@renders` mort) | 1 fichier (~394 l.) | **0** — supprimé |
| shims top-level (`index/texlogos/progressbar/quotes/smart_dashes`) | 5 | **0** — 3 ré-export supprimés, 2 (quotes/smart_dashes) déplacés vers `extensions/` ; entry-points repointés ; groupe `texsmith.renderers` mort supprimé |
| `LaTeXFormatter.__getattr__`/`__getitem__` magiques | présents | **supprimés** (accès explicite `render_template`) |
| `_FallbackConverter` (faux PDF) | présent | **supprimé** (+ flag CLI mort `--no-fallback-converters`) |
| `writers/latex/*.py` | 0 (pré-migration) | **11** (`__init__`, `writer`, `registry`, `state`, `escaper`, `tables` (P3) + `assets`, `media`, `links`, `doi` (helpers relogés P5)) |
| surface src `.py` (working tree, début P5 → fin P5) | 184 fichiers / 43 362 l. | **172 fichiers / 39 238 l.** (**−12 fichiers, −4 124 lignes**) |
| god modules > 1000 l. | 4 (snippet 1777, strategies 1537, render 1169, …) | **4** (snippet 1739, strategies 1537, writer 1428 [issu P3], render 1165) — NON découpés (aucun découpage évident sans risque) |
| tests (passed) | 798 (P3) | **795** (`test_rule_ordering.py` supprimé : testait le `RenderRegistry` mort ; aucune assertion LaTeX relâchée) |

---

## Blocages ouverts

_(vide)_
</content>
