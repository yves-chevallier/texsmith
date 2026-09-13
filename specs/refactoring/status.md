# Refactoring status (2026-09-13)

Where the SOLID / DRY / SSOT / KISS pass on `src/texsmith` stands, what it
decided, and what it has not done. Branch `refactor/00-drop-html-input`, 22
commits on top of `tmark-migration`. Read this, then `AGENT.md`, then
`specs/migration/merge-readiness.md`.

## The frontier, as settled

`~/tmark/design/00-overview.md` states it and the refactoring keeps it:

> **Purity test.** If a function needs a file, a clock, a process or a socket,
> it is either behind the `Loader` trait or it is in TeXSmith.
> **Body test.** If a writer needs to know the template, the font, the package
> list or the page geometry, the concern is TeXSmith's.

tmark's non-goals name slots, templates and build orchestration as TeXSmith's
(`spec/tmark.md` §Header: "that machinery is a processing concern, not
syntax"). Three traits cross its crate boundaries — `Loader`, `Writer`,
`Rule` — and `design/01-architecture.md` asks for an ADR before a fourth.

**The chosen course does not move that frontier.** It generalises the
mechanism that already crosses it: `Loader` is a typed request/response —
Rust asks, Python answers, Rust continues — and the same shape is what the
resource-resolving passes need. No fourth trait, no doctrine reversal.

## Decisions taken

| # | Decision | Why |
| - | -------- | --- |
| R1 | **The `Loader` pattern is generalised, not the frontier moved.** | No fourth trait, no ADR reversal. It is also the only route that drops `ir/`. |
| R2 | **HTML input is deleted, not repaired.** | MkDocs Material is migrating to Zensical and the next MkDocs drops plugins and extensions. Zensical support will be designed against what Zensical emits. |
| R3 | **Refactor before the merge.** | Against the initial recommendation; the merge diff grows, but each step lands on its own branch with its own readable baseline diff. |
| R4 | **The MkDocs plugin follows; breaking changes are fine.** | Nothing is released. This lifts the only hard blocker on unifying the diagnostics. |
| R5 | **`press.sources.bibliography` is the spelling that feeds the `.bib`.** | The root `bibliography:` stays accepted; tmark already relocates it and emits `deprecated-frontmatter-key`. It is also what `tmark lint --fix` rewrites *to*. |

## What shipped

`src/texsmith`: **39 967 → 34 986** lines. 1 232 tests,
`parity.py baseline --check` 196 identical / 54 skipped / **0 differing**,
ruff clean — at every commit.

- **HTML front end gone** (−5 833): `readers/html/`, `extensions/`,
  `Document.from_html`, `InputKind`, `--selector`/`--full-document`/`--parser`
  (the last had been inert since the migration), the plugin's `press.reader`
  branch.
- **Dead code purged** (−1 200): 18 unreferenced symbols, the
  `use_emitter`/`current_emitter` contextvar whose client (the Markdown
  extensions) went in phase 5, the `pdf-metadata` and `minimal_fonts` chains,
  `_overlay_dogear_frame`, the `fold_size` computation that ended in
  `_ = fold_size`, and `parents[4]/"sandbox"/"fonts"` in the font search path.
- **SSOT made enforceable**: one `Span` (the generator imports it, as
  `diagnostics/model.py` always said it must; `diagnostic_span` and its 20
  call sites are gone), one boolean reading (was eleven), one suffix table
  (was six), one HTTP identity (was three), fragment manifests that no longer
  restate what their class owns (all thirteen had drifted).
- **Six bugs fixed**, each with its test: the documented bibliography spelling
  producing no `.bib`; the Typst path swallowing what LaTeX raised; two
  documents from different directories being unrenderable; `margin_style`'s
  own `default` word crashing geometry; `linenums="off"` turning line numbers
  *on*; `--parser` inert.
- **`core/conversion` 4 450 → 3 633**: `debug.py` dissolved (six outside
  packages imported it), bibliography gathered into `core/bibliography`
  (`inputs.py` was 300 lines of it under a name that says "inputs"),
  `typst.py`/`typst_ir.py` merged (they were one module cut in the wrong
  place), one wrapping path, one result DTO, batch state no longer aggregated
  by object identity, `ConversionRequest` actually frozen, `build_pdf` moved
  to `adapters/latex/build.py`, `render` split 406 → 220 lines.

## What remains

Five steps, none started.

**03 · One diagnostics system.** `core/diagnostics.py` (226) and
`texsmith/diagnostics/` (709) still coexist; **20 sites** call
`warning()`/`error()` with no code and no span. The lock is the `FileTable`
with no owner, carried by `getattr(emitter, "files", None)` — a block
duplicated verbatim in two places plus an `isinstance` in a third. R4 lifted
the hard blocker. Pays off immediately: `--diagnostics-json` becomes usable
by an editor and `--strict` becomes discriminating.

**05 · The CLI.** `render()` is **764 lines and 46 parameters**. Extract a
`RequestBuilder` (about 180 lines of business logic leave the CLI, and the
eight cross-mutations of flags go with them). Close the Typst short-circuit —
59 lines rebuilding arguments the request already carries. Make `snippet.py`
(1 489) call `ConversionService.build_pdf`: 44 of its 65 lines are identical
after de-indenting. Delete the three monkeypatch hooks — one is entirely
dead, one patches globally while looking local, one works only because a
re-export shadows a submodule; `service.py:297` already injects properly.

**06 · The pure passes into tmark** — *two repositories, ADR each.*
`tmark-lsp/src/outline.rs:101-135` already partitions a block list by heading
level: factor it into `tmark-ir::sections`, expose `tmark.split(...)`, and
`slots` (247) and `headings` (49) go. Then `include` (283, and `IdAllocator`
with it — the id floor exists only because Python re-parses files that number
from 1), then `var` and `title` (114) as resolve options, on the model of the
`glossary` pass that was deleted by typing a front-matter declaration.

**07 · The request/patch contract** — *two repositories.* The bet.

    tmark    → typed requests   [{node_id, kind, payload}]   media · DOI · link · font
    texsmith → resolutions       {node_id → patch | literal}  I/O · network · cache · build
    tmark    → applies the patch and writes

One contract serves four passes (`assets`, `emoji`, `doi`, `snippet`). It is
typed, it is *finite* — TeXSmith never sees the whole tree — and it is the
**only** route that drops `ir/` (**2 195 lines, untouched**). Migrating the
pure passes alone leaves `ir/model.py` and `codec.py` entirely in place.

**08 · Templates and fragments.** 6 332 lines (`core/templates` 2 952,
`core/fragments` 1 309, `fragments` 2 071). Two complete activation
mechanisms run in parallel with **opposite** conventions on
`implied_packages` (one subtracts, one adds). The `Requires` contract never
replaced the string sniffers it was meant to replace: `callouts` still hunts
`\begin{callout` through every context value, `extra` scans ~40 LaTeX
patterns, and `article` walks the whole context character by character **to
pick the compiler**. "Fragment" means three things and "slot" two, and the
two senses of "slot" exclude each other — one site raises where the other
validates.

## Debts posed, deliberately not paid

- **Numbering sources.** LaTeX resolves the mode from
  `(template_overrides, request.template_options)`, Typst from
  `template_overrides` alone. Four combinations on a test document render
  identically, so unifying cannot be verified on the corpus: it needs its own
  change and its own test.
- **`.ris`.** `snippet.py` collects it as a bibliography source and nothing
  under `core/bibliography` can parse it; it reaches pybtex and fails there.
  `core/sources.py` says so in a comment.
- **`press.frame`.** The same parser is duplicated between `fragments/frame`
  and `snippet.py`. Belongs to step 08.
- **`to_template_fragments`.** A DTO translation that survives because
  `ConversionResult` and `TemplateFragment` genuinely carry different things.
- **Typst without a template** builds no bibliography at all, where LaTeX
  writes `texsmith-bibliography.bib`. Found while writing a regression test.

## How to work on this

**The parity gate is the ratchet, and it earns its keep.** Extracting the
shared slot-writing loop, a text map written as a comprehension over the
returned bodies looked equivalent and was not — two bodies may name the same
slot and their text is *concatenated*, while the body mapping keeps the last.
`examples/colorful` lost a paragraph. **All 1 232 tests passed.**
`parity.py baseline --check` named the differing entry. Run it on every step;
a step whose baseline diff you cannot explain line by line is not finished.

One step, one branch, one readable baseline diff. Changing a page under
`docs/` changes its baseline: re-record it and let the diff be reviewed.

**Three traps this pass fell into, all caught:**

1. A grep truncated by `head` declared a live presenter branch dead
   (`template_overrides` is emitted by `renderer.py`, not the CLI). Its test
   caught it. Search the whole tree, `packages/` included, before deleting.
2. String-keyed registries defeat both static analysis and reading: four of
   the seven `_normalise_*` in `manifest.py` are registered and invoked by no
   manifest, and three are live — a scan of unreferenced symbols gets all
   seven wrong. Exclude decorated definitions, count attribute *loads*, not
   tokens.
3. `--build` is called `build_pdf` in the CLI, so importing a function of
   that name shadowed it with a boolean and ruff then removed the import as
   unused. `'bool' object is not callable`.

## Before merging

Unchanged from `specs/migration/merge-readiness.md`: tmark
`texsmith-migration` → `main` first, then this branch → `master`; the five
`ref:` lines in `.github/workflows/ci.yml`; `vendor/tmark` is still a
gitignored symlink rather than the pinned wheel D8 describes.
