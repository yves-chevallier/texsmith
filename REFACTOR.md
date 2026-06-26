# TeXSmith — Plan de refonte (réduction & modularité)

> Branche : `refactor/ir-migration`. L'API publique peut être cassée.
> Principes (AGENT.md) : pas de shim, pas de duplication, pas de couche de
> compat, SSOT/SOLID/YAGNI/KISS. Après **chaque** lot : `uv run pytest` doit
> rester vert (851 tests à la base) et `uv run ruff check . && ruff format .`.
>
> Convention de statut : `[ ]` à faire · `[~]` en cours · `[x]` fait · `[-]` abandonné (justifié).

## Tableau de bord

| Lot | Thème | Gain LOC visé | Risque | Statut |
|-----|-------|---------------|--------|--------|
| 1 | Suppressions pures (shims/dead/compat) | ~400 supprimés | faible | [x] |
| 2 | Dédup SSOT légère | ~270 supprimés | faible | [x] |
| 3 | Dédup structurelle | ~700 supprimés | moyen | [~] |
| 4 | Refonte architecturale | ~3000 relocalisés | élevé | [~] |

Baseline tests : **851 passed**. Après Lots 1–3 : **849 passed** (−2 tests `Alignment` supprimés), ruff clean.
Réduction nette `src/` à date : **−645 LOC** (791 supprimées / 146 ajoutées), 3 fichiers supprimés, 1 ajouté (`writers/_ir_queries.py`).

---

## Lot 1 — Suppressions pures (faible risque)

### 1.1 Shims & compat
- [x] `adapters/latex/renderer.py:65-72` — supprimer `LaTeXRenderer.register()` (no-op, 0 appelant).
- [x] `core/git_version.py:137-145` — supprimer `format_version` (shim déprécié) + entrée `__all__`.
- [x] `core/templates/session.py:234-235` — supprimer le rejet du kwarg `callbacks`.
- [x] `core/templates/builtins.py:17-19` — supprimer `_ALIASES` (`formal-letter`).
- [x] `fragments/geometry/__init__.py:161` — supprimer alias `getLatex()`.

### 1.2 Dead code
- [x] `core/fonts/__init__.py` — supprimer fichier + dossier (`__all__ = []`, 0 importeur).
- [x] `fragments/__init__.py:1-11` — supprimer namespace mort (`__all__ = []`).
- [x] `core/conversion` — supprimer `SegmentContext`, `AssetMapping`, `segment_registry`, `Document.segments`/`assets`, `runtime_common`, `prefer_inputs`, `slot_inclusions`.
- [x] `ir/nodes.py` — supprimé `CitationMode`/`Cite.mode` et `Alignment`/`from_short` (aucun champ de nœud, aucun writer ne les lit ; tests autoréférentiels retirés). **Conservés** (faux positifs de l'audit, vérifiés vivants/testés) : `NodeVisitor` (testé, API publique), `iter_child_fields` (utilisé en interne), `Figure.placement` (lu par writers/tables), `OrderedList.start` (lu par writer Typst), `Admonition.collapsible` (parsé+testé).
- [x] `ui/cli/commands/templates.py:30-45` — supprimer `_discover_local_templates` dupliqué (shadowé).
- [x] `core/templates/loader.py:271-301` — supprimer bloc mort après `return`.
- [x] `devtools.py:13-18` — supprimer `try/except` inatteignable.

## Lot 2 — Dédup SSOT légère (faible risque)
- [x] Registre d'extensions : `_EXTENSIONS`/`ExtensionSpec`/`available_extensions`/`get_extension_spec`/`load_markdown_extension`/`load_mkdocs_plugin` avaient **zéro consommateur** → tout supprimé (`extensions/__init__.py` réduit à un docstring). `DEFAULT_MARKDOWN_EXTENSIONS` reste la SSOT (~140 LOC).
- [x] Fusionné `core/html_utils.py` → `adapters/html_utils.py` (`strip_html_comments`) ; repointé `conversion/templates.py` ; fichier supprimé.
- [x] `squash_blank_lines` : `core/templates/text.py` était mort (0 importeur) → fichier supprimé ; wrapper garde sa copie utilisée+testée. `_discover_template_variables` : canonique unique dans `context_usage` (`set[str] | None`), wrapper l'importe.
- [-] `_MATH_PAYLOAD_PATTERN` — **déféré** : duplication reader↔writer/escaper, mais le reader ne doit pas dépendre du writer ; ~10 LOC pour un couplage inter-couches discutable. Nécessite un foyer neutre — à traiter avec le découpage des writers (Lot 4).

## Lot 3 — Dédup structurelle (moyen risque)
- [x] `writers/_ir_queries.py` créé : helpers citation/footnote (`_normalise_footnote_id`, `_split_citation_keys`, `_citation_keys_from_payload`, regex DOI) + `_find_image`/`_find_table` partagés ; les deux writers importent au lieu de dupliquer (~110 LOC dédup). Bonus : supprimé le wrapper `_infer_heading_reference` (import direct depuis `links`).
- [x] `BaseFragment` : `build_config`/`inject` deviennent des **défauts concrets** (`config_cls.from_context` / `config.inject_into`) ; retirés des 10 fragments conformes (bibliography, callouts, code, glossary, index, keystrokes, todolist, typesetting, fonts, extra). `frame`/`geometry` gardent leurs corps custom (~120 LOC).
- [x] `templates/common/` : mixin `TemplateContextHelpers` (`_coerce_string`/`_format_authors`) ; article/book/letter en héritent (~90 LOC).
- [-] `strategies.py` : **déféré**. Les `_svg_to_pdf`/`_svg_to_png`/`_run_playwright` ne sont **pas** verbatim (appel `_normalise_svg_for_playwright`, viewport scaled vs non-scaled diffèrent entre SVG/Mermaid/Drawio). La dédup exige un paramétrage à risque comportemental, vérifiable seulement avec playwright/docker runtime. La cascade `_run_with_backends` (comptabilité primary/cli/docker) est la partie la plus délicate. À faire avec des tests playwright en place.
- [-] `BaseFragment._scan_for_tokens` — non traité : les `_detect_*` par fragment diffèrent assez (tokens distincts) ; gain marginal vs risque. À réévaluer.

## Lot 4 — Refonte architecturale (risque élevé)
- [x] Déplacé `core/conversion/glossary.py` → `core/glossary.py` (0 importeur dans la couche conversion ; voisin de `metadata`/`document_date`). Importeurs repointés.
- [ ] **Reste à faire (gros chantiers multi-sessions)** — voir détail ci-dessous.

## Lot 4 — Refonte architecturale (risque élevé)
### Reste à faire — chantiers structurants (par ordre de valeur/risque)

1. **Collapser les 4 couches d'orchestration** → `service.py` (façade) + `core.py` (moteur) ; absorber la boucle de `pipeline.py` + `ConversionBundle`/`LaTeXFragment` ; supprimer l'indirection `convert_document` mono-doc. *(~120 LOC, touche le cœur — exige run complet à chaque étape.)*
2. **Sortir l'orchestration moteur LaTeX** de `ui/cli/commands/render.py:~1065-1216` vers un `core.build_pdf(...)` (logique métier hors CLI ; supprime les hooks monkeypatch `render.shutil/subprocess/run_engine_command`).
3. **Relocaliser `render_typst_document`** (`typst_emit.py`) dans `core/conversion` ; promouvoir les 5 imports privés (`_load_inline_bibliography`, `_build_mustache_defaults`, `_replace_mustaches_in_html`, `_resolve_callout_style`, `_citation_label`) en API publique — supprime le pipeline Typst parallèle.
4. **Fermer la fuite IR** : lower `exercise`/`snippet`/`rich_table` dans le reader (plus de `BeautifulSoup`/`HtmlReader` rappelés depuis les writers, `writer.py:~1173-1294`).
5. **`DoiBibliographyFetcher`/`_DOI_SUPPORT`** (`core/conversion/templates.py:38-40`) — remplacer le cache-global (couture de test) par une injection du fetcher via requête/contexte ; adapter `test_cli_bibliography`. *(reporté du Lot 1.)*
6. **Relocaliser l'orchestration fonts** (~870 LOC : `_ensure_ctan_sty`/`_ensure_plex_fonts`/`_prepare_fallback_context`…) de `fragments/fonts/__init__.py` vers `texsmith/fonts/`, laissant un fragment fin (~120 lignes).
7. **Découper les god objects** (relocalisation, pas suppression) :
   - `writers/latex/writer.py` (1428) → `spans.py` + `containers.py` + fusion `media.py` → cœur ~550.
   - `ui/cli/commands/render.py` (1225) → options dans `_options.py`, branches HTML/Typst extraites (cf. #2/#3) → ~600.
   - `core/templates/manifest.py` (1039) → [x] `languages.py` extrait (tables babel/BCP-47 + mappers, −108 L → 931 ; `runtime.py` repointé). [ ] `normalisers.py` : **bloqué par dépendance circulaire** (les normalisers décorés référencent `TemplateAttributeSpec` défini dans manifest, et manifest doit les importer pour peupler le registre) — exige de sortir le registre `_ATTRIBUTE_NORMALISERS` + `TemplateAttributeSpec` dans un module socle d'abord.
   - `adapters/plugins/snippet.py` (1739) → package `snippet/` (cache / imagerie / parsing).
   - `adapters/transformers/strategies.py` (1537) → une classe/fichier + dédup playwright (cf. Lot 3 déféré).
   - `adapters/latex/engines/__init__.py` (768) → sortir les runners aux (biber/index/glossaries) vers `aux.py`.
   - [x] `adapters/latex/engines/latex/log.py` (720→500) → `LatexLogRenderer` sorti dans `log_render.py` (244) ; `stream_latexmk_output` importe le renderer paresseusement pour éviter le cycle ; patterns/types partagés restent dans `log`.
   - `core/conversion/core.py` (681) → extraire résolution d'options (emoji/code/fragments). [x] `core/documents.py` (637→547) → `core/heading_analysis.py` (les 2 `HTMLParser` imbriqués sortis en classes module ; `_HEADING_TAGS` mort supprimé).
8. **`_MATH_PAYLOAD_PATTERN`** (reporté du Lot 2) — un foyer neutre importable par reader+escaper, à décider lors du découpage des writers.

---

## Journal
- (init) Baseline 851 tests verts. Plan établi.
- Lot 1 ✅ — shims (`LaTeXWriter.register`, `git_version.format_version`, kwarg `callbacks`, `_ALIASES`, `getLatex`), dead code (`core/fonts/`, machinerie segments/assets/`runtime_common`/`prefer_inputs`/`slot_inclusions`, `CitationMode`/`Alignment`, doublons `_discover_local_templates`/loader/devtools). 849 tests.
- Lot 2 ✅ — registre d'extensions mort supprimé, `core/html_utils.py` fusionné, `text.py` mort supprimé, `_discover_template_variables` unifié. 849 tests.
- Lot 3 (partiel) ✅ — `writers/_ir_queries.py`, défauts `BaseFragment`, mixin `templates/common`. strategies déféré. 849 tests.
- Lot 4 (entamé) — `glossary.py` relocalisé ; `languages.py` extrait (manifest 1039→931) ; `heading_analysis.py` extrait (documents 637→547). Gros chantiers documentés ci-dessus. 849 tests.