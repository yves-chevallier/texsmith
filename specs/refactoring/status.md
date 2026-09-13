# Refactoring status (2026-09-13)

Where the SOLID / DRY / SSOT / KISS pass on `src/texsmith` stands, what it
decided, and what it has not done. Branch `refactor/00-drop-html-input` (23
commits on `tmark-migration`), then `refactor/03-diagnostics` (8 more). Read
this, then `AGENT.md`, then `specs/migration/merge-readiness.md`.

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

## Step 03 · One diagnostics system — **done**

Branch `refactor/03-diagnostics`, 8 commits. 1 238 tests, parity 196/54/0,
ruff clean at every commit. `src/texsmith` 34 986 → 35 141 (+155: the code
table grew by eleven entries and twenty call sites went from one line to
five).

`core/diagnostics.py` and `texsmith/diagnostics/` were **not** two
implementations of one thing — two *layers* of it, cut so the lower could not
be used without the upper. The emitters are now `diagnostics/emitters.py` and
the package imports nothing from `core`; `raise_conversion_error` moved to
`core/exceptions.py`, which is the seam that made the cut possible.

An emitter is a **presenter**: `render` and `event`. The sink collects,
deduplicates, and owns the `FileTable`. `DiagnosticEmitter.warning`/`error`,
`legacy_diagnostic` and `LEGACY_CODE` are deleted — every finding carries a
code, and `emit_diagnostic(emitter, code, message, span=…, exc=…)` is the one
way a stage that holds an emitter reports one.

**The file table had no owner, and that was a bug, not a smell.** `span.file`
is a third of `Diagnostic.key`, the identity the sink deduplicates on, so the
file a finding belonged to was decided by `getattr(emitter, "files", None)`:
under `LoggingEmitter` a batch numbered 0, 1, 2 and under `NullEmitter` — the
library default, which had no table — 0, 0, 0. Two findings in two files then
collided. `NullEmitter` became a `SinkEmitter` that renders nothing, so every
emitter has a table and the `getattr` is gone.

Three things fell out of it, each with its test:

- **A diagnostic inside a `snippet` fence named the host page.** The nested
  document parsed against a private table and took id 0 — the id the host
  already held — so a finding in a fence rendered as the host's path at the
  fence's line number. A location that exists and is wrong.
- **The MkDocs plugin built three file tables**, one per page plus a second
  emitter per page to render against it. Every page was file 0; its
  long-lived emitter never saw a page record.
- **`_warn_add_to_path` and half of `_emit_dependency_warning` were not in
  the diagnostics system at all** — `warnings.warn`, so invisible to
  `--diagnostics-json` and `--strict`, and fatal under `PYTHONWARNINGS=error`,
  which `--strict` replaced.

Two dead `getattr(emitter, "info", None)` branches in the LaTeX asset writer
called a method no emitter defines in either repository.

**A step that was proposed and is wrong: "one sink per run".**
`pipeline._forwarding_sink` looks like a duplicate collector and is not. It
is a *scope*: the per-render sink over `document.files`, forwarded to the
run's emitter. `ctx.files` must stay the document's table, because the
`include` pass registers included files in it, and `convert_documents`
legitimately accepts documents parsed separately (`test_template_renderer.py`
does). Instrumenting every render in the suite settled it: 74 of 183 had a
document table that was not the emitter's, all of them `NullEmitter` — and
tracing *those* is what found the snippet bug. Do not collapse the two sinks
without first deciding whether `convert_documents` should still accept
documents it did not parse (step 07's contract).

## Step 05 · The CLI — **done**

Branch `refactor/05-cli`, 5 commits. 1 282 tests, parity 196/54/0, ruff clean
at every commit. `render()` 757 → 721 lines (body 582 → 546); `snippet.py`
1 505 → 1 449.

**The Typst short-circuit was a bug, not only duplication.**
`render_typst_document` took four fields of the request as separate arguments
and built a `ConversionRequest` out of them, so every other field reverted to
its default and the context took a bare `GenerationStrategy()`. Six options
were inert under `--format typst` — `--hash-assets`, `--convert-assets`,
`--no-copy-assets`, `--manifest`, `--http-user-agent`, `--debug-ir` — and
`--include-path` was worse than inert: the include failed and its text was
lost, where LaTeX resolved it. **250 recorded renderings did not notice,
because no corpus entry passes any of those flags.** The baseline is a strong
ratchet for what it covers; that is its edge.

**The three monkeypatch hooks, and the shadow behind them.**
`commands/__init__.py` did `from .render import render`, which rebinds the
package's `render` attribute from the *submodule* to the *function*: the
dotted path meant one thing to `import` and another to `getattr`. The command
then hung `shutil` and `run_engine_command` off the function object as a patch
surface. `render.shutil` was dead — `render.py` calls `copy2` and `rmtree`,
never `which`, and the eight tests patching `render_cmd.shutil.which` were
patching the stdlib module, redundantly with the line below each of them.
`build_pdf` already takes the runner as a parameter.

**`snippet._compile_pdf` was a second copy of `adapters.latex.build.build_pdf`**
that had drifted: no `if choice.backend == "tectonic"` guard around the
binary acquisition, and a `getattr(render_result, "template_context", …)`
probe for a field `TemplateRenderResult` does not have. Verified against the
real engine, not the mocks: the `snippet` and `docs/examples/snippets` entries
build through Tectonic in both backends and render identically.

**The flags now argue in one place.** `core/conversion/policy.py` holds the
four settings a flag and the front matter both claim (`strict_enabled`,
`declared_template`, `numbered_setting`, `deprecated_level`), each stating its
own precedence; the `--deprecated` feature moved there whole from
`conversion/pipeline.py`, which hosted it and used none of it.
`ui/cli/plan.py` holds the reconciliation between the flags themselves —
pure, so it is testable without invoking the command. 43 tests where there
were none.

Two accidental semantics it exposed, both **pinned by a test and left alone**:

- `--attribute x=1` is refused without a template, and the check runs before
  `-o out.pdf` can imply a build and a build can imply `article` — so
  `--attribute x=1 -o out.pdf` is an error and `--attribute x=1 --build` is
  not.
- `--build` names `article` for **either** backend; a build *inferred* from
  `-o out.pdf` names one only for LaTeX. The command has two "default the
  template" lines and only the second carries the `output_format != "typst"`
  guard. Unifying it changes what `--format typst -o out.pdf` renders, so it
  needs its own change and its own test.

## What remains

Three steps, none started.

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
- **Diagnostic message style.** The `Diagnostic.message` docstring asks for
  "one sentence, no trailing period, names the construct"; half the sites
  open with a capital and a verb (`Mermaid diagram '…' not found`) and half
  lower-case and name the construct first (`unresolved moustache '…'`). The
  twenty converted in step 03 follow the docstring. Unifying the rest is a
  pass over ~25 strings with no structural content; it changes no baseline
  (diagnostics are stderr) so only the tests gate it.
- **Four API pages render as empty documents.** `docs/api/cli`,
  `bibliography`, `transformers` and (before it was deleted) `markdown` have
  nothing in their body but `::: module` mkdocstrings directives, which TMark
  parses as a run of empty containers: the PDF export of those pages is a
  title and nothing else. The site renders them correctly — only the export
  is affected. Either the writers should keep an unknown container's source,
  or those pages need prose.
- **The two "default the template" lines of the render command.** See step 05:
  `--build` names `article` for either backend, a build inferred from
  `-o out.pdf` only for LaTeX. Pinned by a test, not unified.
- **The event channel rides on the diagnostics emitter.** `event()` and
  `record_event` report progress (`asset_fetch`, `doi_fetch`,
  `template_attributes`) and have nothing to do with findings, but they are
  members of `DiagnosticEmitter` and `format_event_message` lives in
  `diagnostics/emitters.py`. Splitting them belongs with step 05, which owns
  the CLI's reading of both.

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

**Six traps these passes fell into, all caught:**

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
4. **Counting a system's call sites by its own vocabulary misses the sites
   that bypass it.** Step 03's twenty `warning()`/`error()` calls were the
   ones that *used* the emitter; two more reported through `warnings.warn`
   and two through `getattr(emitter, "info", None)`, a method no emitter
   defines. Grep for the escape hatches — `warnings.warn`, `print`, a bare
   `logger`, `getattr` on a method name — not only for the API.
5. **The parity gate answers one direction only.** It re-renders what the
   corpus lists and compares; it never asked whether a recorded baseline still
   has a corpus entry. Two pages deleted during the migration kept their
   committed `.tex` and `.typ` for twenty-three commits. `baseline --check`
   now reports `orphaned-baseline` as a failing status. The other half of the
   same blind spot is still open: a flag no corpus entry passes is not covered
   at all, which is how six options stayed inert under `--format typst`.
6. **`tests/` is not a package.** A helper in `tests/conftest.py` cannot be
   imported (`from .conftest import` fails, `from conftest import` resolves
   to `tests/passes/conftest.py`). Shared test classes go in a module with a
   distinct name — `tests/emitters.py` — and the fixture wrapping them in
   `conftest.py`.

## Before merging

Unchanged from `specs/migration/merge-readiness.md`: tmark
`texsmith-migration` → `main` first, then this branch → `master`; the five
`ref:` lines in `.github/workflows/ci.yml`; `vendor/tmark` is still a
gitignored symlink rather than the pinned wheel D8 describes.
