# Merge readiness (2026-09-14)

What a reviewer needs before merging `texsmith-migration` into `main` in the
tmark repository and the refactoring stack into `master` here. Measured on
TeXSmith `refactor/07-request-contract` and tmark `353311f`.

## The order is not negotiable, and it is stricter than it was

**tmark merges first.** It always had to, for the six `ref: texsmith-migration`
lines in `.github/workflows/ci.yml`. It is now a hard runtime dependency as
well: TeXSmith no longer generates its own mirror of the IR — it imports
`tmark.ir`, which the wheel ships (31 import sites). A TeXSmith built against a
tmark without `python/tmark/ir/` does not start.

    1. tmark   texsmith-migration → main
    2. texsmith  the refactoring stack → master
    3. the six `ref:` lines become `main`, in their own commit

## Size, against `master`

| | master | this stack |
| - | -----: | ---------: |
| `src/texsmith`, Python lines | 43 018 | **33 075** |
| tests (`tests/` + `packages/`) | 19 961 | 18 651 |
| tests collected | 1 017 | **1 335** |
| runtime dependencies | 24 | 22 |
| largest module | `snippet.py`, 1 768 | `strategies.py`, 1 492 |

The production package is **9 943 lines smaller than `master`** — 23 % — while
doing more. The diff is 1 170 files, +317 232 / −31 824; the insertions are
almost entirely the committed regression baseline (3.3 MB of `.tex`/`.typ`
under `tests/parity/baseline/`, 196 recorded entries), the design notes under
`specs/`, and the corpus fixtures.

`markdown`, `pymdown-extensions` and `python-markdown-math` are gone; `tmark`
is the one addition.

## State

- TeXSmith: **1 335 tests** pass, `ruff check` and `ruff format --check` clean.
- tmark: **321 tests**, `clippy -D warnings` clean, `cargo fmt --check` clean,
  plus **48 Python tests** under `crates/tmark-py/tests` (the IR model
  generator moved there with the generator it checks).
- `scripts/parity.py baseline --check` (the CI gate): **196 identical, 54
  skipped, 0 differing**, and it now also fails on an `orphaned-baseline` — a
  recorded entry the corpus no longer renders.
- Every example builds; the documentation site builds with its PDF export.

## What a reviewer should look at

1. **The stack is five branches, one per step, each with its own readable
   baseline diff.** `specs/refactoring/status.md` is the index: what each step
   decided, what it measured, and what it deliberately did not do. Read it
   before the code.

       refactor/00-drop-html-input  →  03-diagnostics  →  05-cli
                                    →  08-fragments    →  07-request-contract

2. **Two steps were withdrawn or re-scoped on evidence, not abandoned.** 06
   (moving passes into the core) contradicts `spec/tmark.md` §Header, which
   assigns heading offsets and title promotion to TeXSmith by name. 07 (the
   request/patch contract) was rejected as drafted — five independent analyses
   found its central claim false — and replaced by three small moves that are
   done. `specs/refactoring/07-synthesis.md` carries the reasoning;
   `design/decisions/0008-resolution-requests.md` in tmark is marked rejected
   with what survives it.

3. **The IR mirror moved repositories.** `src/texsmith/ir/` (2 195 lines) and
   `scripts/gen_ir_models.py` (822) are deleted; tmark generates and ships
   `tmark.ir.{model,codec,walk}`. `Span` moved with it and is now defined once,
   from the schema, rather than declared in TeXSmith's diagnostics and imported
   back by the generated models. This is the change most worth reviewing on
   the tmark side.

4. **The spec and the code were written together.** Challenges C27–C50 were
   decided and implemented in the same commits, by the same agents. An
   independent conformance pass over the spec sections they touched is the one
   review this work has not had.

5. **The writers were never diffed against the 0.6 output.** The parity harness
   compared readers while both existed; it now gates one rendering against a
   recorded baseline. `specs/migration/parity-triage.md` lists what the
   comparison found while it could still be made.

6. **Two copies of `texsmith.typ`** — the shipping one under
   `src/texsmith/templates/common/` and the crate's reference under
   `crates/tmark-writers/assets/` — must define the same functions with the
   same signatures. Nothing generates one from the other.

7. **The `FRAGMENTS` contract spans both repositories.** A macro added on the
   tmark side fails `test_every_provides_entry_is_defined` here until the
   fragment defines it. That failure is the intended alarm, but it couples the
   two releases.

## Breaking changes a consumer sees

Nothing is published, so these are recorded rather than deprecated. The
`CHANGELOG.md` entries carry the detail.

- `texsmith.core.diagnostics` → `texsmith.diagnostics`;
  `DiagnosticEmitter.warning`/`error` removed in favour of `emit_diagnostic`;
  a custom emitter subclasses `SinkEmitter` and implements `render`.
- `texsmith.ir` → `tmark.ir`.
- `render_typst_document(document, request, …)` takes the request positionally.
- `ConversionRequest.embed_fragments` → `embed_documents`, and the MkDocs
  plugin option with it; `LaTeXFragment` → `RenderedDocument`;
  `ConversionBundle.fragments` → `.documents`.
- `FragmentPiece.slot` → `FragmentPiece.variable` (and the `fragment.toml` key).
- `--strict` is discriminating: findings that carried the free-form `texsmith`
  code now carry real ones, so a run that passed may now fail.

## Still open before a release

- The six `ref: texsmith-migration` lines in `.github/workflows/ci.yml` become
  `main` once tmark merges.
- `vendor/tmark` is a gitignored symlink locally and a checkout in CI. A
  release replaces it with the published wheel (`tmark>=0.X,<0.X+1`), which is
  what `specs/tmark-migration.md` D8 describes and nobody has done yet. The
  wheel must be one that ships `python/tmark/ir/`.
- The version is still `[Unreleased]` in `CHANGELOG.md`; releases here are cut
  in their own commit and tag.
- Four API pages (`docs/api/cli`, `bibliography`, `transformers`) render as
  empty documents in the PDF export: a body made only of `::: module`
  mkdocstrings directives is a run of empty TMark containers. Cosmetic, and
  recorded in `specs/refactoring/status.md` §Debts.
