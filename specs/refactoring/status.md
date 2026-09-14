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

## Step 09 · Warnings into the sink — **done**

Branch `refactor/09-warnings-to-sink`, stacked on `refactor/07-request-contract`.
1 345 tests, ruff clean at every commit. Three new codes: `font-fallback`,
`fragment-manifest`, `metadata-invalid`.

Step 03 found two `warnings.warn` calls in the font pipeline and fixed those;
the rest — 24 call sites across nine files — stayed outside the diagnostics
system, invisible to `--strict` and `--diagnostics-json` the same way. This
step decided each one: route it through `emit_diagnostic` where a run's
emitter can be threaded to the call site, or say plainly why it can't and
fall back to the module's own logger, which at least survives
`PYTHONWARNINGS=error` and standard `logging` configuration. Nothing found
here was dead.

**The grep the task started from over-counted by one, in one direction and
under by one in the other.** `fonts/provisioning.py` has eight `warnings.warn`
calls, not nine; the ninth is `fragments/fonts/__init__.py:61`, the CTAN
try/except that wraps `_ensure_ctan_sty` from the fragment's `inject_into` —
conceptually the same "font could not be prepared" family, in the adjacent
file. `grep -rn 'warnings.warn' src packages` turns up a 24th site the task's
file list did not name, `ui/cli/commands/render.py:111`; the total of 24
holds, the per-file split does not.

**Threading the emitter meant widening two contracts, not adding a shim.**
`render_fragments` (`core/fragments/__init__.py`) already runs inside
`wrap_template_document`, which has held an `emitter` parameter since step 03
— it just never passed it to `render_fragments`, and `BaseFragment.build_config`/
`.inject` had no parameter to carry it to a fragment's own `from_context`/
`inject_into`. Both gained a keyword-only `emitter: DiagnosticEmitter | None
= None`, default-ignored by the nine fragments that don't need it (`geometry`
and `frame` override the two methods and now discard the parameter the same
way they already discard `overrides`; the other seven use `BaseFragment`'s
default, which does the same). Only `FontsFragment` forwards it, down through
`FontsConfig.from_context`/`.inject_into` into `fonts/provisioning.py`'s
`_normalise_family`, `_ensure_noto_color_emoji`, `_ensure_openmoji_black`,
`_ensure_plex_fonts`, `_ensure_ctan_sty`, `_prepare_fallback_context` and
`_prepare_mono_font` — the whole call graph the eight (plus one) font warnings
live in. `tests/test_fragments.py::test_ctan_package_failure_reaches_the_sink_end_to_end`
drives a real document through `TemplateSession` with a failing download to
prove the wiring reaches that far, not just the unit-level functions.

The acronym-conflict warning in `core/context.py` threaded the same way, on a
much shorter path: `DocumentState.remember_abbreviation`/`.remember_acronym`
gained the keyword, `core/fragments/activation.py`'s `apply_requires` forwards
it, and its one caller with a real emitter — `render_ir_document` in
`core/conversion/pipeline.py` — already had one in scope. The Typst path's
second call to `apply_requires` (`conversion/typst.py::_render_acronyms`, a
redundant reformat of a document already processed once) keeps the default
`None`: whatever it would have warned about already fired on the first pass.

**Where no single emitter reaches the call site, it stays off the sink.**
Eleven of the 24 are module-level utilities — `core/metadata.py`'s
`normalise_press_metadata` (11 call sites, several before any `Document` or
emitter exists), `core/document_date.py`'s `format_date` (behind the four
templates' `prepare_context`, which carries no emitter), `core/git_version.py`
(five sites, consumed by both of the above) and `ui/cli/commands/render.py`'s
crossref-inventory delivery, which now matches the sibling crossref failures
already on the module logger in `conversion/service.py` and
`adapters/latex/build.py`. Threading an emitter through all of `metadata.py`'s
callers alone would touch the CLI's front-matter merge, `conversion/policy.py`,
`conversion/typst.py`, `core/documents.py` (four sites), the template manifest
and the snippet plugin — a redesign of front-matter resolution, not a warnings
cleanup. Each of these eight call sites got `logger = logging.getLogger(__name__)`
and a `logger.warning(...)` in place of `warnings.warn`; three more in
`core/fragments/__init__.py`'s `_discover_entry_points` (a broken
`texsmith.fragments` entry point) got the same treatment, for the same
reason — that code runs once, building the module-level `FRAGMENT_REGISTRY`
singleton, before any run's emitter exists.

**One call site is not a document finding at all and was left alone.**
`core/templates/manifest.py:197`'s `register_attribute_normaliser` warns a
*template package author* who re-registers a normaliser name without
`override=True` — a Python import-time collision notice for a library
extension point, the same category as the stdlib's own warnings about
shadowed registrations. It is not `DeprecationWarning` (nothing about it is
deprecated) and it is not a per-document finding, so it keeps `warnings.warn`
as a plain `UserWarning`.

| # | Site | Decision | Code / mechanism |
| - | ---- | -------- | ----------------- |
| 1 | `fonts/provisioning.py:135` (`_normalise_family`) | routed | `font-missing` |
| 2 | `fonts/provisioning.py:190` (`_ensure_noto_color_emoji`) | routed | `font-fallback` |
| 3 | `fonts/provisioning.py:222` (`_ensure_openmoji_black`) | routed | `font-fallback` |
| 4 | `fonts/provisioning.py:281` (`_ensure_plex_fonts`) | routed | `font-fallback` |
| 5 | `fonts/provisioning.py:398` (`_ensure_ctan_sty`, download failed) | routed | `font-fallback` |
| 6 | `fonts/provisioning.py:544` (`_prepare_fallback_context`, emoji unavailable) | routed | `font-fallback` |
| 7 | `fonts/provisioning.py:648` (`_prepare_fallback_context`, font not on disk) | routed | `font-fallback` |
| 8 | `fonts/provisioning.py:826` (`_prepare_mono_font`) | routed | `font-fallback` |
| 9 | `fragments/fonts/__init__.py:61` (`FontsConfig.inject_into`) | routed | `font-fallback` |
| 10 | `core/fragments/__init__.py:275` (entry point failed to load) | kept — module logger | no emitter at registry-construction/import time |
| 11 | `core/fragments/__init__.py:294` (entry point dir has no `fragment.toml`) | kept — module logger | same as above |
| 12 | `core/fragments/__init__.py:304` (entry point resolves to neither) | kept — module logger | same as above |
| 13 | `core/fragments/__init__.py:518` (`should_render` raised, `FragmentDefinition`) | routed | `fragment-manifest` |
| 14 | `core/fragments/__init__.py:548` (`should_render` raised, `BaseFragment`) | routed | `fragment-manifest` |
| 15 | `core/context.py:74` (`remember_abbreviation`, conflicting definition) | routed | `metadata-invalid` |
| 16 | `core/templates/manifest.py:197` (`register_attribute_normaliser`) | kept — unchanged | library extension-point `UserWarning`, not a document finding |
| 17 | `core/metadata.py:148` (`normalise_press_metadata`) | kept — module logger | 11 call sites, several pre-`Document`; would carry `frontmatter-root-overrides-press` if an emitter ever reaches it |
| 18 | `core/document_date.py:163` (`_resolve_locale`) | kept — module logger | behind four templates' `prepare_context`, none carry an emitter |
| 19 | `core/git_version.py:44` (`git_describe`, no repo) | kept — module logger | consumed by `document_date`/`document_version`, same reach problem |
| 20 | `core/git_version.py:63` (`git_describe`, no metadata) | kept — module logger | same |
| 21 | `core/git_version.py:81` (`git_commit_date`, no repo) | kept — module logger | same |
| 22 | `core/git_version.py:93` (`git_commit_date`, no metadata) | kept — module logger | same |
| 23 | `core/git_version.py:102` (`git_commit_date`, unparseable output) | kept — module logger | same |
| 24 | `ui/cli/commands/render.py:111` (`_deliver_reference_inventory`) | kept — module logger | matches sibling crossref-inventory logging in `conversion/service.py`, `adapters/latex/build.py` |

12 routed to `emit_diagnostic`, 11 kept on a module logger, 1 kept as an
unchanged library `UserWarning`, 0 dead.

## The five steps, resolved

Three were done, one was withdrawn on the evidence, and one was re-scoped
until it dissolved into three small moves that are also done. Each step is its
own branch, stacked in order:

    refactor/00-drop-html-input   →  03-diagnostics  →  05-cli
                                  →  08-fragments    →  07-request-contract

`src/texsmith` **39 967 → 33 082**. 1 335 tests, `parity.py baseline --check`
196 identical / 54 skipped / **0 differing**, ruff clean — at every commit of
every branch.

**06 · The pure passes into tmark** — **the premise does not survive the
spec; do not start it as written.**

The step was stated as: factor `tmark-lsp/src/outline.rs`'s heading
partition into `tmark-ir::sections`, expose `tmark.split(...)`, "and `slots`
(247) and `headings` (49) go", then `include` (283), then `var` and `title`
(114). That is 693 lines claimed. Read against `spec/tmark.md` and the code,
what can move is **ten**.

`spec/tmark.md` §Header assigns the work by name:

> Headings are relative: **TeXSmith** aligns messy multi-file hierarchies
> automatically (per-fragment offset from the shallowest heading, plus the
> template slot base, plus `press.base_level`), and promotes the first
> heading to the document title […]. **That machinery is a processing
> concern, not syntax.**

That sentence *is* `headings.py`, line for line — offset from the shallowest
heading, the template's slot level, `document.base_level` — and it *is*
`title.py`, which only applies the promotion decision. Neither can move
without reversing the sentence. `design/00-overview.md` §Non-goals puts
"Templates, preambles, … build orchestration" on TeXSmith's side too.

Of `slots.py`'s 244 lines, exactly `_section_end` — **10 lines** — is the
generic partition. The other 234 are the selector grammar (`#id`, bare text,
`@document`, `*`), matching by id then by text, the nested-header diagnostic,
the claiming order, `strip_heading` from the manifest and `flatten` from the
front matter: template machinery, which the frontier assigns here.

**Correction (2026-09-14).** The withdrawal stands, but this paragraph measures
the wrong quantity, as the first-principles analysis in `07-synthesis.md`
points out. What an outline query removes is not `_section_end`'s ten lines: it
is TeXSmith's *tree walk* for five scalars per heading, and with it the `id()`
reconciliation at `passes/highlight.py:176` — `document.bodies` and
`document.ir` kept in step by Python object identity, because `slots`
partitioned objects instead of selecting indices — and the per-body re-encode
of the whole document at `core/conversion/bodies.py:194`. The primitive is
worth more than ten lines and now has three users. See the synthesis, move 2.

So the whole step reduces to sharing a ten-line partition across a repository
boundary, in two languages, and `~/tmark/AGENTS.md` answers that directly:
"**DRY across languages, not within reason.** Duplicating three lines is
fine; duplicating a table of node names between Rust, Python and a grammar is
not." A new `tmark-ir` module, a new binding, an ADR and a cross-repository
coupling to delete ten lines of Python is the wrong trade.

`include` (283) is the one piece with a real argument — the splice itself is
tmark's shape and `Loader` exists for exactly this — but its search path
(`--include-path`, `press.include_paths`, the site's `pymdownx.snippets`
base) is TeXSmith's, so what would move is the splice, not the pass. `var`
(76) could become a resolve option only by shipping the template overrides
into Rust, which is the same frontier question step 07 poses properly.

**Recommendation:** drop 06 as a step. Fold the `include` splice question
into 07, which already asks whether a typed contract should carry TeXSmith
data into the core, and which is the only route that drops `ir/`.

**07 · The resolution contract** — *two repositories.* The bet. **Assessed
and re-scoped**, not started: `specs/refactoring/07-resolution-contract.md`
here, `design/decisions/0008-resolution-requests.md` in tmark, both proposed.

    core → requests    [{node_id, kind, payload}]      what needs resolving
    host → patches     {node_id: replacement | drop}   what to put there
    core → sections    [{node_id, level, id, text,     the top-level outline
                         first_block, last_block}]

Two corrections to the sketch this entry used to carry.

**Four passes is the wrong scope.** They are 990 lines; seven passes remain,
1 083 lines, and six of them construct `model.*` nodes — so `ir/` (2 195)
does not go, and a request/patch contract would run *beside* a Python tree
walk. Two mechanisms in parallel is what step 08 spent three commits removing
from the fragment activation; it is a new defect, not a half-migration.

**The contract is not limited to I/O passes.** The constraint is per-node
replacement versus restructuring, and ten of eleven passes are the former —
`highlight` (`CodeBlock` → `Div` + `RawBlock`), `scripts` (`Str` → a run of
`Span{script}`), `var`, `title` (a patch that removes), `include` (one node →
N blocks, and `Loader` exists for it). The eleventh is `slots`, which never
needs the tree either: it needs an index of the top-level headers to match a
selector against, and a write of a named block range. Hence `sections`.

**Superseded by `07-synthesis.md` (2026-09-14).** Five independent analyses —
one briefed to defend the contract — all found that it does not drop `ir/`
either: a patch *is* IR, so TeXSmith keeps the node types, the field names, the
id space and the span rules in order to construct one. ~500-600 generated lines
survive and the two-repository coupling with them. Three passes cannot fit the
shape at all (`RefItem` has no id; `assets` inserts a sibling block; `scripts`
needs a whole-document text query).

The sceptic's measurement reframes it: the mirror is **three days old**, the
schema has changed **7 times ever**, and the total hand-written cost is **~37
lines in `walk.py`, once**. One schema change made TeXSmith smaller.

**The direction, three small moves instead of the bet:**

1. **Ship `tmark.ir` from the wheel** (~1 day). `crates/tmark-py/pyproject.toml`
   already sets `python-source = "python"` and `gen_stubs.py` already generates
   Python from Rust. TeXSmith deletes 2 195 lines *and* the generator. This is
   the whole of the contract's stated benefit, without the contract.
2. **`tmark.outline(doc)` as its own small ADR** (~2 days). Three users
   (`slots`, `title`, `headings`); removes the `id()` reconciliation at
   `highlight.py:176` and the per-body re-encode at `bodies.py:194`.
3. **Id and span custody** (~1 day) — the one argument that survived the
   sceptic, and a correctness one: a span copied onto synthesised text is a
   location that exists and is wrong.

Then stop and measure. `tmark.edit`/`edit_many` already exist in the shipped
binding; if requests are ever revisited, `select` + `edit_many` lands pass by
pass, under the rule the analysis produced: **a response carries an answer — a
path, a key, a font name, a token stream, a typed failure — never a tree.**

**08 · Templates and fragments** — **done**, branch `refactor/08-fragments`.

**Done: the opposite conventions on `implied_packages`.** `apply_requires`
subtracted every package an active contract loads itself; `inject_requires`,
three lines down the same call chain, added them all back. Two functions of
that name, two modules, the identical set by two routes, opposite sign. The
net was `ts-extra` loading what the fragments had already loaded: `graphicx`
and `xcolor` twice in the preamble of **68 of the 129** recorded LaTeX
renderings. A third mechanism sat between them — `FRAGMENT_OWNED_PACKAGES`,
nine hardcoded names overlapping the sixteen computed ones in three. The rule
is now stated once, in `extra_packages_from_requires`: what the bodies named,
less what an active contract provides. Baseline: **707 deletions, no
insertions**, and the four PDF-baseline entries build identically through
Tectonic, ink coverage included.

**Done: the two senses of "slot".** Two checks, both reporting on
"Fragments", with opposite conditions — `core/fragments/__init__.py` raised
when the slot *was* declared, `conversion/renderer.py` when it was *not*.
Between them they reject every value; they never fired together only because
they read different dictionaries. `FragmentPiece.slot` is now
`FragmentPiece.variable`, which the line under the first check already called
it: a fragment injects into a template *variable* (`extra_packages`), a
document is assigned to a *slot* (`mainmatter`).

**Measured, deliberately not changed — the string sniffers are not
vestigial.** The memo assumed `Requires` had failed to replace them. It has,
in production: over the whole 250-entry corpus the legacy branch
(`contract_active(...) is None`) is **never taken**. But it is reachable —
ten hits in the test suite, all through `wrap_template_document` — because a
caller that builds a `DocumentState` without running the IR passes, and wraps
a template around LaTeX it produced itself, has no `Requires` to read. The
sniffers serve *that* caller. Deleting them is a decision about whether that
caller is supported, not a cleanup.

Two measurements for whoever takes it:

- `ts-extra`'s ~40 patterns contribute exactly **four** packages beyond what
  `Requires` names, corpus-wide: `seqsplit` (96×) and `float` (88×), both
  added *unconditionally* and so not sniffing at all, plus `amsmath` (67×,
  triggered by any `$` anywhere in any context string — a price in prose
  fires it) and `tabularx` (1×).
- `article`'s character-by-character walk of the whole context **is
  load-bearing**: it switches 25 of 93 renders from pdflatex to lualatex, on
  Greek, Cyrillic, Arabic, box-drawing and arrow characters. It is not a
  candidate for deletion, and an IR-derived answer would be incomplete —
  template attributes and front matter carry text the IR never saw.

**Done: "fragment" meant two unrelated things**, and they collided on three
consecutive fields of `ConversionRequest` — `embed_fragments` (inline each
converted document) beside `enable_fragments` / `disable_fragments` (turn a
`ts-*` contract package on or off). The sense that is not a `ts-*` package is
renamed for what it is: `embed_documents`, `RenderedDocument`,
`ConversionBundle.documents`. The MkDocs option follows.

**Done: the `press.frame` parser**, which the debts list assigned here — see
above.

**`core/templates` (2 951) is untouched, and this pass found no reason to
touch it.** The one defect the memo pointed at there is trap 2's seven
`_normalise_*`, and checking them confirms the trap rather than a bug: three
(`babel_language`, `bcp47_language`, `margin_style`) are invoked by a bundled
manifest, and the other four (`paper_option`, `orientation`, `callout_style`,
`code_options`) are registered for template authors and documented in
`docs/guide/templates/index.md`. None is dead. Restructuring 2 951 lines for
size alone is churn; give the next pass a demonstrated defect first.

## Debts posed, deliberately not paid

- **Numbering sources.** LaTeX resolves the mode from
  `(template_overrides, request.template_options)`, Typst from
  `template_overrides` alone. Four combinations on a test document render
  identically, so unifying cannot be verified on the corpus: it needs its own
  change and its own test.
- **`.ris`.** `snippet.py` collects it as a bibliography source and nothing
  under `core/bibliography` can parse it; it reaches pybtex and fails there.
  `core/sources.py` says so in a comment.
- ~~**`press.frame`.**~~ Paid in step 08. The copy in `snippet.py` is gone;
  asking `FrameConfig` exposed that the grammar disagreed with itself —
  `press.frame: dogear` was rejected by the error message that lists it,
  while `{mode: dogear}` worked, because the two branches that read a mode
  word each spelled `_MODE_WORDS` out again and differently.
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

**Seven traps these passes fell into, all caught:**

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
6. **`build/parity/check` used to accumulate.** `_write_diffs` wrote this
   run's diffs into a directory it never cleared, so a later run that found an
   entry identical left the earlier run's diff file sitting beside the fresh
   ones. Reading them together showed changes no run had found — prose edits
   attributed to a change that touched only LaTeX packages. The directory is
   cleared per run now; a `.diff` in it is this run's.
7. **`tests/` is not a package.** A helper in `tests/conftest.py` cannot be
   imported (`from .conftest import` fails, `from conftest import` resolves
   to `tests/passes/conftest.py`). Shared test classes go in a module with a
   distinct name — `tests/emitters.py` — and the fixture wrapping them in
   `conftest.py`.

## Before merging

`specs/migration/merge-readiness.md` carries the detail, re-measured against
this stack. The order is tmark `texsmith-migration` → `main` first, then the
stack → `master`, and it is **stricter than it was**: TeXSmith no longer
generates its own IR mirror, it imports `tmark.ir` from the wheel at 31 sites,
so a TeXSmith built against a tmark without `python/tmark/ir/` does not start.

Then the **six** (not five) `ref: texsmith-migration` lines in
`.github/workflows/ci.yml` become `main`, in their own commit; and
`vendor/tmark` is still a gitignored symlink rather than the pinned wheel D8
describes — and the wheel it pins must be one that ships the IR.
