# TeXSmith on TMark — migration plan

Status: in progress, 2026-09-11. Companion of `~/tmark/design/11-roadmap.md`
(milestones M4 and M5 are the tmark side of this plan). When the two
documents disagree, the tmark roadmap wins for what tmark builds and this
document wins for what TeXSmith builds. The difficulties of §6 each have a
design note under `migration/` (`web-profile.md`, `fragment-contracts.md`,
`writers-and-passes.md`, `examples-migration.md`, `python-ir-and-passes.md`);
where the notes disagree, `migration/decisions.md` settles it and lists the
implementation waves. `migration/baseline.md` records the state of the
examples before any change. Integration branches: `tmark-migration` here,
`texsmith-migration` in `~/tmark`.

## 1. Where things stand

**tmark** (Rust, `~/tmark`): M1–M3 are implemented. Parser, IR with a
committed JSON schema, canonical printer (`fmt`), registries and
resolution, lint, CLI, language server, VS Code extension. Three crates are
three-line skeletons: `tmark-writers` (M4), `tmark-py` and `tmark-wasm`
(M5). The printer already round-trips the 93 pages of TeXSmith's
documentation. M1 is formally open on one TeXSmith item: the caption line
*after* a table is not rendered by TeXSmith 0.6, so the normal form the
printer emits does not build "unchanged in meaning".

**TeXSmith** (Python, 0.6.0): the pipeline is

```text
.md ─Python-Markdown + 46 extensions─▶ HTML ─HtmlReader (bs4)─▶ texsmith.ir ─LaTeXWriter / TypstWriter (Jinja partials)─▶ slots ─templates + fragments─▶ .tex/.typ ─engines─▶ PDF
.html (MkDocs page.content) ────────────▶ HTML ─┘
```

`texsmith.ir` is a hand-written Python model of the same tree the Rust
crate defines (the Rust catalogue was derived from it). `specs/tmark.md` is
a stale copy of `~/tmark/spec/tmark.md` (2 268 differing lines).

**The syntaxes are not unified today.** TeXSmith 0.6 parses the *shipping*
spellings, not the canonical ones the spec and the printer use:

| Canonical (spec, `tmark fmt`) | What TeXSmith 0.6 parses |
| ----------------------------- | ------------------------ |
| `::: figure {#fig:x}` … `:::` containers | nothing (`:::` is not implemented anywhere in `src/`) |
| `{counter}(prefix:key)`, sugar `#(prefix:key)` | `#{prefix:key}` |
| `@key`, `@[k1; k2]` citations | `[^key]`, `^[k1,k2]` |
| `{raw latex}(…)`, ```` ```latex raw ```` | `{latex}[…]`, `/// latex … ///` |
| `{aside}[…]`, `{aside side=left}` | `{margin}[…]{l\|r\|o\|i}` |
| `{include}(file)` | `--8<-- "file"` (pymdownx.snippets) |
| `Table: …` *after* the table; `Figure:`/`Listing:` lines | `Table:` before; `/// caption` |
| `@gls:term` | `[](gls:term)` |
| `{index registry=r}[…]`, `{index main=true}` | `{index:r}[…]`, `{index}[…]{b}` |
| `press.declare.*`, `press.sources.*` | top-level `counters:`, `bibliography:`, `crossrefs:`, `glossary:` |

Where the two agree (attribute lists, `@label` references, `!!!`
admonitions, `yaml table` fences, `__smallcaps__`, math, footnotes,
abbreviations, definition lists) parity is the only question.

## 2. Target architecture

```text
.md ──tmark.parse──▶ IR (JSON) ──TeXSmith passes (I/O)──▶ IR' ──tmark.resolve(loader)──▶ Resolved
                                  include · exec · assets · DOI · Var · slots · fonts
                                                                                    │
                     ┌──────────────────────────────────────────────────────────────┘
                     ▼
        tmark.write(IR', "latex"|"typst"|"html") ──▶ Body { text, map, requires }
                     │
        TeXSmith: Requires → fragments → preamble; body → template slots; engines → PDF; source map → SyncTeX
```

Two rules keep the boundary honest (`~/tmark/design/00-overview.md`): a
function that needs a file, a clock, a process or a socket is TeXSmith's
(or hides behind `Loader`); a writer that needs to know the template, the
font, the packages or the geometry is asking for a fragment contract, not
an option.

What TeXSmith keeps: templates, fragments, fonts, engines (Tectonic,
latexmk, Docker), bibliography output (pybtex, DOI fetch, CSL), diagram
conversion (mermaid, draw.io, SVG), includes, executed fences, cross-document
inventory writing, the CLI, the MkDocs companion. What TeXSmith loses:
Python-Markdown and every extension, the HTML reader as the main path, the
hand-written IR, the two Python writers, the counter and cross-reference
resolvers, the Jinja partials as a rendering mechanism.

## 3. Decisions to take before coding

Each one changes the shape of the work. A recommendation is given; the
alternative is named so the choice is explicit.

**D0 — Where syntax unification happens.** *Recommended: in the tmark
reader, not in the Python-Markdown extensions.* Teaching the legacy
extensions the canonical spellings (a `:::` block processor, `{counter}(…)`,
`@key` citations, `press.declare.*`, …) is throwaway work that phase 5
deletes, and it would take weeks. The legacy path receives exactly one
syntax change, the caption line after a float (0.1), because tmark's M1
gate needs it and the parity harness compares it first. Until 0.7 an
author who writes canonical TMark builds it with 0.6 through `tmark fmt
--profile mkdocs`, whose purpose is precisely to print the shipping
spellings (`~/tmark/design/04-printer.md`, "TeXSmith's companion
extensions render them"); that profile is a stub today and becomes a phase 1
deliverable. The visible unification for users happens at the flip (4.3):
the docs, the `writing-texsmith` skill and the examples switch to canonical
spellings, `tmark lint --fix` rewrites their documents, and each legacy
spelling follows the horizon of the spec's Appendix D.

**D1 — Who owns the LaTeX/Typst/HTML writers.** *Recommended: tmark
(`tmark-writers`), as designed.* The alternative (keep the Python writers,
feed them the tmark IR) is faster to reach but leaves two rendering
implementations forever (the editor preview needs a Rust writer anyway,
ADR 0005) and keeps 2 200 lines of Python that mirror what Rust will do.
Cost of the recommendation: the Jinja partial mechanism disappears as a
rendering layer (see D3), pygments and font-script detection become
contracts and IR passes, and template-scoped `@writes` hooks (0.4.1) lose
their meaning.

**D2 — How the IR crosses the boundary.** *Recommended: JSON dicts through
`tmark-py`, typed on the Python side by models generated from
`crates/tmark-ir/schema/ir.json`* (ADR 0003). `datamodel-code-generator`
produces pydantic v2 models (pydantic is already a dependency); a script in
TeXSmith regenerates them from the pinned wheel's `tmark.schema("ir")` and
CI fails when the committed file drifts. `walk` / `map_tree` are rewritten
over the generated tagged unions (`"type"` discriminator). The
hand-written `texsmith/ir/nodes.py` is deleted.

**D3 — What replaces the Jinja partials.** *Recommended: fragment
contracts.* Today every construct renders through a `.tex` Jinja partial
that templates and fragments may override (`latex.template.override`,
`required_partials`). A Rust writer cannot call Jinja. The design already
answers: the writer emits a fixed macro or environment per construct
(`\tscallout`, `tscode`, `\tskeys`, `\tslead`, …) and names the fragment
that provides it in `Requires.fragments`; the fragment carries the
`\newcommand`/`\newenvironment`. Overriding a partial becomes redefining a
macro in LaTeX, which is what LaTeX authors expect. Structural output
(`\emph`, lists, `tabularx`, `figure`) is emitted directly. The 55 partials
in `adapters/latex/partials/` are triaged one by one: structural → writer,
styled → fragment macro, template-only (`pagestyle`, `exercises_solutions`,
`choices`) → stays a partial used by the template wrapper.

**D4 — Numbering and resolution ownership.** *Recommended: tmark-registry.*
It already allocates TeXSmith-numbered series (declared counters, theorem
kinds), reads `.bib` files and `refs.json` inventories through `Loader`,
resolves `@` references and anchor links, and honours
`ResolveOptions.start` for a series continuing across documents. TeXSmith
deletes `core/counters.py` and the resolver half of `core/crossrefs.py`,
keeps the inventory *writer* (`build_payload`, `attach_pages`,
`harvest_aux`, `relocate_inventory`) and fixes the staleness hash tmark
waits on. Multi-document builds (`mkdocs` books, `multi-document` example)
feed each document's final numbers into the next `ResolveOptions.start`.

**D5 — HTML input.** *Recommended: keep `.html` input as a secondary
reader that produces the tmark IR, and move the MkDocs companion to the
Markdown source.* The MkDocs plugin today captures `page.content` (rendered
HTML) and converts it; with tmark it should parse `page.file.abs_src_path`
(or `page.markdown` after `on_page_markdown`) and run the same passes as
the CLI. The `HtmlReader` (bs4, 2 300 lines) is retargeted to emit the
generated models instead of `texsmith.ir` and kept for `texsmith page.html`
and for sites that are not MkDocs. Alternative: drop HTML input. Not
recommended yet; the reader is the only path for Material-rendered
constructs the TMark parser will never see (annotations, `snippets` URL
rewriting).

**D6 — Front matter and moustaches.** tmark types the keys it reads
(`title`, `authors`, `press.declare`, `press.sources`, `press.features`, …)
and keeps the rest in `extra`. TeXSmith keeps validating `press.*`
(`core/metadata.py`) on `extra` plus the typed keys. `{{ key }}` in the body
becomes a `Var` node; `_replace_mustaches_in_html` becomes an IR pass
substituting `Var` → `Str`. Moustaches inside the front matter stay a
TeXSmith concern (they run before parsing today and keep doing so).

**D7 — Diagnostics.** One shape: tmark's `Diagnostic { code, severity,
span, message, fix, related }`. TeXSmith's `DiagnosticEmitter` and the
`warnings.warn` calls in counters/crossrefs are replaced by emitting the
same records (Python passes create them with a span when they have one) and
printing them `file:line:col: severity code: message`. `PYTHONWARNINGS=error`
is replaced by `--strict` / `press.features.strict`.

**D8 — Packaging and versioning.** TeXSmith depends on the `tmark` wheel
(PyPI, maturin, abi3 for CPython ≥ 3.10, manylinux/macOS/Windows) with a
compatible-release pin (`tmark>=0.X,<0.X+1`). The IR JSON root carries
`"tmark": "0.x.y"`; TeXSmith refuses a major mismatch at import. The
generated Python models are regenerated and committed for each tmark bump.
Development: the `uv` workspace adds a path source for `~/tmark` so
`maturin develop` in TeXSmith's venv tests unreleased crates. The Docker
image installs the wheel.

## 4. Phases

Each phase leaves both repositories usable. Nothing is deleted before the
parity gate of phase 4 is green.

### Phase 0 — Unblock and align (TeXSmith, small)

| # | Task | Done when |
| - | ---- | --------- |
| 0.1 | Render a caption line *after* a table, figure or listing (`Table: … {#id}` below the float, `Figure:` and `Listing:` likewise) through the existing HTML reader. | `tmark fmt spec/tmark.md` builds with TeXSmith unchanged in meaning; tmark closes M1. |
| 0.2 | Delete `specs/tmark.md`; `specs/README.md` points at `~/tmark/spec/tmark.md`; the `spec` target of the `Makefile` builds the tmark copy. The docs site fetches or vendors the spec at build time if it must be published. | One copy of the spec exists. |
| 0.3 | Add `tmark check` and `tmark fmt --check` over `docs/` and `examples/` to TeXSmith's CI, advisory (non-blocking) at first. | The report is visible on every PR. |
| 0.4 | Construct gap audit (section 5 of this document) turned into spec challenges or M5 items in tmark, one per row. | Every row has an owner. |
| 0.5 | Freeze: no new syntax in the Python-Markdown extensions. New syntax goes through the spec and the tmark parser first. | Written into `AGENT.md`. |

### Phase 1 — tmark M4: writers (tmark)

Order from `~/tmark/design/13-handoff.md`: HTML, then LaTeX, then Typst.

| # | Task | Done when |
| - | ---- | --------- |
| 1.1 | `FRAGMENTS` table in `tmark-ir::registry`: every contract name, the macros it provides, the packages it implies. Derived from the partial triage of D3. | The table exists and TeXSmith's fragment loader reads it. |
| 1.2 | `tmark-writers`: `Writer`, `Body`, `Requires`, `SourceMap`, the zero-width whitespace post-pass, `common.rs` escaping tables ported from `writers/latex/escaper.py` (368 lines of hard-won cases: carets, accents, math heuristics) and `writers/typst/escaper.py`. | Snapshot per fixture and per backend. |
| 1.3 | HTML writer. | CommonMark suite expectations match; the LSP preview shows it. |
| 1.4 | LaTeX writer, construct by construct, driven by the parity harness of phase 4 (run early, on `docs/` and `examples/`). Tables (`tabularx`/`longtable`/`multirow`, width discount for `\tabcolsep`, 0.5.4), figures with short captions and `\label` after `\caption`, footnotes, index entries, glossary acronyms, keystrokes, callouts, code (`tscode` contract), lists, definition lists, epigraphs, margin notes, math verbatim. | Parity diff empty on the corpus, modulo a documented allow-list. |
| 1.5 | Typst writer. Math through `mitex` as today, equation labels natively (the current Python writer's rule), or the small LaTeX-math translator the design plans. | Same corpus builds with `typst compile`. |
| 1.6 | `tmark write FILE --to … --map`, `tmark schema inventory` (B4). | CLI documented. |
| 1.7 | `Profile::Mkdocs` made real: prints the shipping spellings of section 1 (the bridge of D0). | `tmark fmt --profile mkdocs docs/**/*.md` builds with TeXSmith 0.6 unchanged in meaning. |
| 1.8 | Typst preview in `tmark-lsp` (ADR 0005). Independent of TeXSmith; may slip. | — |

### Phase 2 — tmark M5: Python bindings (tmark)

| # | Task | Done when |
| - | ---- | --------- |
| 2.1 | `tmark-py`: `parse`, `parse_with`, `resolve`, `lint`, `format`, `write`, `edit`, `schema`, `fixes`; `Loader` protocol wrapped at the boundary; `pythonize` for JSON. Add `resolve` explicitly (the six-function list of `09-bindings.md` folds it into `write`; TeXSmith needs `Resolved` between its passes and the writer for numbering, `Requires` previews and diagnostics). | `pip install tmark` gives the module and the `tmark` console script. |
| 2.2 | maturin + `pyproject.toml`, abi3 wheels in CI (manylinux 2_28 x86_64/aarch64, macOS universal2, Windows x64), sdist. | Wheels on PyPI (or TestPyPI) for a tagged version. |
| 2.3 | Python stubs (`.pyi`) generated from the schema, shipped in the wheel. | `pyright` sees typed signatures. |
| 2.4 | Version handshake: `tmark.__version__`, IR root `"tmark"` field, `tmark.schema_hash()`. | TeXSmith can check compatibility without parsing. |

### Phase 3 — TeXSmith: the IR path behind a flag (TeXSmith)

| # | Task | Done when |
| - | ---- | --------- |
| 3.1 | `scripts/gen_ir_models.py`: `tmark.schema("ir")` → `src/texsmith/ir/model.py` (pydantic v2, tagged unions). CI check that the file matches the pinned wheel. `walk`, `map_tree`, `children`, `plain_text` rewritten over it. | `tests/test_ir_*` pass on the generated models. |
| 3.2 | `texsmith.readers.tmark`: text → `tmark.parse` → models. `--reader tmark` / `--reader html`, default `html` until phase 4. `Document` stores the IR, not HTML (`_html` becomes a property of the html reader only). | A document round-trips through the new reader. |
| 3.3 | IR passes, one module each under `texsmith/passes/`, pure functions `Document → Document` plus diagnostics, ordered: `include` (splice, `FileId` per file, asset base path), `var` (moustaches), `snippet` (snippet-preview fences → nested build → `Image`; later the same module hosts opt-in executed fences), `assets` (`.drawio`, `.svg`, mermaid, emoji fonts → converted files, `src` rewritten, `Requires.assets` consumed), `doi` (pending DOI citations → bibliography entries), `slots` (split by heading id/text into template slots; replaces `extract_slot_fragments` on HTML), `headings` (base level, offset, title promotion, numbering flags), `scripts` (font-script detection: wrap runs in `Span{script=…}` so the writer emits `\text<slug>{}`), `glossary` (front-matter acronyms → `Abbr`). | Each pass has unit tests on IR fixtures, no HTML anywhere. |
| 3.4 | Resolution: `tmark.resolve(doc, loader, options)` with a `Loader` backed by TeXSmith's path resolution; `ResolveOptions.start` from the previous document of a multi-document build; `.bib` paths from CLI and front matter. Inventory writer moved to `texsmith/crossrefs/inventory.py`, hash algorithm fixed and documented. | `examples/counters`, `examples/multi-document` and the crossrefs tests pass on the new path. |
| 3.5 | Writing: `tmark.write(doc, backend, options)`. `Requires` drives fragment activation (replaces `DocumentState.has_index`, `has_bibliography`, `shell_escape`, `index_terms`, `citations`, …). Bodies land in template slots; `wrap_template_document` unchanged. Source map → `%` line markers behind `--synctex-md`. | The `article`, `letter`, `paper`, `book` templates render from bodies. |
| 3.6 | Fragments carry the macros of the `FRAGMENTS` table (`ts-callouts`, `ts-code`, `ts-keystrokes`, `ts-glossary`, `ts-index`, `ts-bibliography`, `ts-typesetting` for `\tslead`, epigraph, margin notes, progress bars). Partials retained only for template scaffolding. | `required_partials` is gone from every bundled template; `latex.template.override` documented as macro redefinition. |
| 3.7 | Typst path on the same passes (`core/conversion/typst.py` shrinks to template wrapping and `typst compile`). | `examples/typst-*` build. |
| 3.8 | HTML reader retargeted to the generated models (D5). | `tests/test_html_reader.py` passes on the new models. |
| 3.9 | MkDocs companion: parse the page source with tmark, run passes, share one `Resolved` across the site (`ResolveOptions.start` chained in nav order), emit bodies per book. For the *site* side, replace the `counters` and `index` MkDocs plugins by an `on_page_markdown` hook that runs `tmark.format(profile="mkdocs")` with references expanded to links and numbers (see difficulty R8). | `examples/mkdocs` builds site and PDF. |

### Phase 4 — Parity gate and flip (TeXSmith)

| # | Task | Done when |
| - | ---- | --------- |
| 4.1 | `scripts/parity.py`: for every page of `docs/` and every example, render with `--reader html` and `--reader tmark`, normalise (whitespace, comment lines, asset hashes), diff the `.tex`/`.typ`; compile both; pixel-diff PDFs with `pymupdf` (already a dependency). Allow-list file for intended differences with a reason each. | The harness runs in CI. |
| 4.2 | Close the diff, construct by construct. Every allow-list entry is either a fixed bug in the old path (documented in the changelog) or a spec decision. | Diff empty, allow-list reviewed. |
| 4.3 | Flip the default to `tmark`; `--reader html` stays for `.html` inputs and one release as an escape hatch. Changelog entry with the visible changes. Docs, examples and the `writing-texsmith` skill switch to canonical spellings; a migration page lists each legacy spelling, its replacement and `tmark lint --fix`. | Release 0.7.0. |

### Phase 5 — Delete (TeXSmith)

| # | Task |
| - | ---- |
| 5.1 | Delete `texsmith/extensions/*` (all 17 Markdown extensions; keep `extensions/tables/schema.py` only if validation stays in Python, see R6), `adapters/markdown/`, the HTML-rewriting half of `adapters/plugins/snippet.py` (the nested-build half becomes the `snippet` pass), `writers/latex/`, `writers/typst/` (except `build.py`, `diagrams.py`), `adapters/latex/renderer.py`, `adapters/latex/formatter.py` (Jinja rendering of partials), `core/counters.py`, the resolver half of `core/crossrefs.py`, `ir/nodes.py`, `ir/visitor.py`. |
| 5.2 | Dependencies removed: `markdown`, `pymdown-extensions`, `python-markdown-math`, `pylatexenc` (check), `emoji` (if the pass uses tmark `Str` scanning only), `beautifulsoup4` only if D5's alternative is chosen. Added: `tmark`. |
| 5.3 | Docs: `docs/syntax/*` rewritten against the spec's canonical spellings with the sugar noted; `docs/guide/plumbing/pipeline.md` rewritten; `docs/api/handlers.md` (`@reads`/`@writes`) replaced by "IR passes and fragment contracts"; `AGENT.md` rewritten (it still describes the pre-0.4 `adapters.handlers` DOM pipeline); the `writing-texsmith` skill updated. |
| 5.4 | Tests: the HTML-in tests are replaced by IR-in tests; snapshot tests of bodies move to tmark's fixtures; TeXSmith keeps integration tests (CLI, templates, builds, passes). |
| 5.5 | Release 0.8.0; tmark closes M5. |

## 5. Construct gap audit

What TeXSmith renders today versus what the tmark parser produces now
(`~/tmark/design/02-syntax.md`, "not implemented yet, deliberately", and
the spec's Appendix C). Each row needs an owner in phase 0.4.

| Construct (TeXSmith today) | In tmark now | Action |
| -------------------------- | ------------ | ------ |
| Attribute lists, roles, containers, data fences, `@` refs, `#[]` index, `#()` counters, captions, admonitions `!!!`/`???`, def lists, abbreviations, footnotes, math, moustaches, comments, smallcaps, mark/sub/sup/keys/strike, yaml tables, `mermaid`, `latex raw`, include | yes | parity only |
| Critic markup (`{--…--}`, `{++…++}`, `{==…==}`, `{>>…<<}`, `{~~a~>b~~}`) — `Span role=critic-*` | no (M5) | tmark M5; until then literal, flag in parity allow-list |
| Progress bars `[=45% "label"]` — `ProgressBar` node | no (M5) | tmark M5 (`ProgressBar` is in the spec) |
| Tabbed `=== "Tab"` — `Div role=tabbed-set/tab` | no; spec lists `tabbed` under PyMdownX compat only | decide: drop for print (render as titled sections) or add container `::: tabs`; spec challenge |
| Task lists `- [x]` — `role=task-marker` | tokenizer has GFM task lists; `ListItem.task` | parity only |
| Fancy lists (`a.`, `i.`, `#.`) — `OrderedList.style` | no (M5) | tmark M5 |
| Inline footnotes `^[…]` | no (M5) | tmark M5 |
| Grid tables | no (M5) | tmark M5 |
| Wiki links `[[page]]`, `[[Page\|Label]]` (shipping) | no (M5) | tmark M5 |
| Citations `[^key]`, `^[k1,k2]`, `^[10.1000/doi]` (multi_citations, footnote shadowing) | no; `@key` is canonical and the GFM footnote construct never forms a `Note` without a definition, so `[^key]` never reaches the IR | the most common breaking change in existing documents; tmark needs a tokenizer rule (M5 item "footnote-versus-citation shadowing") or a `lint --fix` that rewrites `[^key]` → `@key` when the key is in the bibliography |
| Snippets `--8<-- "file"` (pymdownx.snippets, also the MkDocs URL rewriting) | no; `{include}(file)` is the replacement | deprecate `--8<--`, print a `deprecated` fix to `{include}`; the URL rewriting stays in the MkDocs companion |
| Snippet previews (```` ```snippet ```` YAML fences rendered to PDF/PNG by a nested build, `adapters/plugins/snippet.py`) | not a construct; a data fence lowers to `CodeBlock{lang=snippet}` | TeXSmith pass: `CodeBlock{lang=snippet}` → nested build → `Image`; the 1 768 lines shrink to the build part |
| `---` alone renders `\clearpage`, not a rule | `HorizontalRule` | writer option or a `ts-typesetting` macro `\tsdivider`; decide in the partial triage |
| Drop caps `:[A](Natoly)`, Material `:material-…:` icons | no | spec challenge or drop |
| TeX logos (`LaTeX`, `XeLaTeX` words → `\LaTeX`) — `TexLogo` node | no | decide: a `{tex}` role, or a TeXSmith `Str` pass keyed on a feature; spec challenge |
| Emoji `:smile:`, Material icons `:material-…:` — `Span role=emoji`, `icon` partial | spec says `Str` (E class) | TeXSmith pass over `Str` (OpenMoji/Noto pipeline already keys on codepoints); icon shortcodes need a decision |
| Smart dashes, smart symbols, smart quotes (`Quoted`) | `Quoted` in the catalogue; dashes are `Str` | check the parser emits `Quoted`; else M5 |
| `\text{}` in prose (`latex_text`), invisible chars, `missing_footnotes` | n/a (TeXSmith work-arounds for Python-Markdown) | delete |
| `md_in_html`, `pymdownx.blocks.html`, raw HTML | `RawInline`/`RawBlock format=html`, dropped by LaTeX | decide what `<div markdown>` users get: nothing (they write `:::`) |
| `pymdownx.blocks.caption` (`/// caption`) | deprecated sugar, lowered | parity only |
| Details/collapsible `???` | `Admonition` with `collapsed` | parity only |
| Margin notes (`ts-marginnote`) — `MarginNote{side}` | `Aside{side}` | rename on the Python side |
| Multicolumn `Div role=multicolumn`, epigraph `Div role=epigraph`, `regex` spans, `script` spans, `label` spans, `counter` spans | not constructs: HTML-reader roles | become `Div{name}`/`Span{attrs}` from containers, or passes (`script`), or resolution (`label`, `counter`) |
| Inline code highlighting `` `#!py x` ``, `{code py}` | yes | parity |
| Executed fences (`python image`, `python table`) — *not shipping*; TeXSmith runs no user code today | `Image{generate=…, code=…}` | new feature, not migration: a TeXSmith `exec` pass, opt-in, sandboxed; out of the parity gate |
| `Space` nodes | parser never emits them | writers and passes must not assume them |

## 6. Difficulties and risks

**R1 — The writers are the long pole, and they are not in Python.** The
Python writers are 2 200 lines plus 55 partials plus the escapers, and they
encode five years of LaTeX corner cases (the changelog is the evidence:
`\leavevmode` before a counter label in a cell, the `\tabcolsep` discount,
`\label` after `\caption`, short captions, `longtable` in a float, capital
Greek in math alphabets — that last one is a fragment, not a writer). Every
one of them must be found again in Rust, and the parity harness is the only
way to find them. Mitigation: build the harness first (phase 4.1 before
1.4), port `escaper.py` test cases as Rust unit tests, keep the old path
runnable until the diff is empty.

**R2 — Partials are a public extension point.** Templates ship
`latex.template.override` partials and `required_partials`; third-party
templates (exam, thesis, poster) may override `figure.tex` or `heading.tex`.
D3 removes that. Mitigation: the fragment-contract macros are the new
extension point and are documented before 0.7; every bundled template is
converted; a deprecation note names the replacement macro for each partial.
Template-scoped `readers`/`writer` hooks (0.4.1) are removed with a
changelog entry; custom constructs are `::: name` containers rendered by a
fragment macro `\tsdiv{name}` or a Python pass.

**R3 — Two IR definitions during the transition.** Until phase 5 the
generated models and `texsmith.ir.nodes` coexist, and the HTML reader
produces the old one. Mitigation: retarget the HTML reader early (3.8) so
that one model exists on the Python side as soon as the flag lands; the
names already agree (`Aside`/`MarginNote`, `Ref`/`Cite` are the renames).
Node ids are not dense (tmark handoff) and restart per included file: passes
must allocate new ids above the maximum of *all* files, and the include pass
must re-key `FileId`.

**R4 — Things the Rust writer cannot do become passes or contracts, and
some are awkward.** Pygments highlighting needs Python: the writer emits
`tscode` and the `ts-code` fragment decides `minted`/`listings`/`pygments`;
for `pygments` TeXSmith must post-process the body (find `tscode`
environments, run Pygments, substitute) or pre-render highlighted LaTeX into
a `RawBlock` before writing. The second is cleaner: a `highlight` pass turns
`CodeBlock` into `RawBlock{format=latex}` when the engine is `pygments`,
keeping `inline_breaks` (0.6.0) in Python. Font-script detection (`\text<slug>`
wrappers on moving arguments, Noto fallback selection) becomes a pass that
wraps `Str` runs in `Span{script=…}`; the writer emits the macro; the
fragment declares the fonts from `Requires` plus the pass's summary. Emoji:
same shape.

**R5 — Slots are extracted from HTML today.** `extract_slot_fragments`
selects headings by CSS selector on the rendered HTML. On the IR it is a
split of `Document.blocks` by `Header` id or text, but slot selectors in
front matter (`press.slot.abstract: "#abstract"`) are CSS-flavoured.
Mitigation: keep `#id` and heading-text selectors, drop CSS classes, warn on
anything else.

**R6 — Table validation lives in Python (876 lines of pydantic).** tmark
ported `TableModel` without validation ("No validation is ported"). Either
tmark grows the validation with diagnostics (`table-span-overlap`,
`table-width-sum`, …), which is the right home since the LSP wants them, or
TeXSmith re-validates the model it receives. Recommendation: tmark, as an
M4 item; until then a Python validation pass on the generated model.

**R7 — The `tmark` wheel is a new hard dependency with a native build.**
Users on unusual platforms (Alpine/musl, PyPy, 32-bit) lose TeXSmith unless
sdist builds work, which needs a Rust toolchain. Mitigation: abi3 wheels for
the main triples, a musllinux wheel if cheap, and an explicit error message
at import. The Docker image and `uv` lock must both be exercised in CI. A
second consequence: TeXSmith's bug-fix cadence for syntax issues now depends
on a tmark release; a path-source dev workflow and a fast tmark patch
release process are part of the plan, not an afterthought.

**R8 — The MkDocs site side has no parser of its own.** MkDocs renders with
Python-Markdown; TMark constructs (`@fig:x`, `#(fw:x)`, `::: figure`,
captions) are invisible to it. Today TeXSmith's own extensions render them
on the web (`counters` and `index` MkDocs plugins, the `references`
extension). After phase 5 those extensions are gone, so the `mkdocs`
profile must do more than print sugar: it must *expand* what the web cannot
resolve (references → `[FW-10](#fw-watchdog)`, counter items → text plus an
anchor, captions → `figure`/`figcaption` HTML, index entries → nothing)
using a site-wide `Resolved`. That is a lowering profile, not a printing
profile, and `Profile::Mkdocs` is a stub today. It is the least designed
part of the whole migration; it needs its own design note in tmark before
phase 3.9.

**R9 — HTML input is a second front door.** The `HtmlReader` recognises
Material HTML (annotations, tabs, `<details>`, snippet blocks, `data-ts-*`
tables). If it is kept (D5) it must emit the generated models and stay in
parity with the tmark constructs it mirrors; if it is dropped, MkDocs users
lose the only way to convert a page that depends on third-party Markdown
extensions. Either way it is a maintenance line that the migration does not
remove. Decide per release; the plan keeps it.

**R10 — Behaviour changes that are not bugs.** The parser is CommonMark,
Python-Markdown is not: lazy continuation lines, list indentation, HTML
blocks, `_` in words, `~` and `__` under the strict profile, entity
decoding (C22), attribute lists needing a host, escaped `\@` and `\#`. User
documents will render differently. Mitigation: `tmark lint` over the corpus
before the flip, a "migration" page listing the differences, and
`--reader html` for one release.

**R11 — Diagnostics and spans.** Today warnings carry a file name at best.
With spans, a warning from a pass (missing asset, failed DOI) should point at
the node; passes must carry `Span` through when they rewrite nodes, and the
include pass must map spans of included files. The source map only survives
if every pass preserves `meta`.

**R12 — Typst math.** The Python writer renders LaTeX math through `mitex`
and special-cases labelled equations. The tmark design plans a translator
"or `raw` with a diagnostic". Keeping `mitex` is the zero-risk choice for
phase 1.5; the translator is a later improvement, not a migration item.

**R13 — Tests.** 101 test files, 1 017 tests, fixtures as inline strings,
no snapshot framework. Many feed HTML to the reader or assert LaTeX
substrings from the Python writer. Roughly: reader tests → drop or retarget
(R9); writer tests → become tmark `insta` snapshots per fixture; pipeline,
template, fragment, engine, CLI tests → keep. Expect about a third of the
files to be rewritten, and the parity harness (4.1) to be the first golden
suite the project has had.

**R14 — Two repositories, one feature.** A syntax change now touches the
spec, the parser, the printer, a fixture, the writers, the bindings, the
generated Python models, a TeXSmith pass, the docs. The process in
`~/tmark/AGENTS.md` (spec first, fixture second) must be mirrored in
TeXSmith's `AGENT.md`, and a single issue tracker label should follow a
feature across both repositories.

## 7. Critical path and sequencing

```text
0.1 caption-after ──▶ tmark M1 closed
0.2–0.5 (parallel, a day)
1.1 FRAGMENTS + partial triage ──▶ 1.2 common ──▶ 1.3 HTML ──▶ 1.4 LaTeX ◀──── 4.1 parity harness (built first)
                                                            └──▶ 1.5 Typst
2.1–2.4 bindings (parallel with 1.4 once 1.2 exists; TeXSmith needs parse/resolve before write)
3.1 models ──▶ 3.2 reader ──▶ 3.3 passes ──▶ 3.4 resolve ──▶ 3.5 write ──▶ 3.6 fragments ──▶ 3.7 typst ──▶ 3.8 html ──▶ 3.9 mkdocs
4.2 close diff ──▶ 4.3 flip (0.7.0) ──▶ 5.x delete (0.8.0)
```

Rough sizing, in agent-days of focused work, to be revised after 1.4 starts:
phase 0: 2; phase 1: 15–25 (the LaTeX writer alone is 10+); phase 2: 4;
phase 3: 15–20 (passes 6, resolve 2, write and fragments 5, mkdocs 4);
phase 4: 5–10 of diff closing; phase 5: 3. The MkDocs web profile (R8) is
unsized until its design note exists.

## 8. What to do first

1. Phase 0.1 in TeXSmith (caption after the float): small, unblocks tmark,
   and is the first construct the parity harness will compare.
2. The parity harness (4.1) on the *current* pipeline, so it exists before
   the first Rust writer line: `docs/` + `examples/` → `.tex` per page,
   normalised, committed as a baseline.
3. The partial triage (D3, 1.1): a table of the 55 partials with their
   destination. It settles the `FRAGMENTS` contract and is needed by both
   repositories.
4. The `mkdocs` profile design note (R8), because it is the only part with
   no design and it decides whether the Python-Markdown extensions can be
   deleted at all.
