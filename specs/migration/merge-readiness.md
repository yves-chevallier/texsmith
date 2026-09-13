# Merge readiness (2026-09-13)

What a reviewer needs before merging `tmark-migration` into `master` here and
`texsmith-migration` into `main` in the tmark repository. Measured on
TeXSmith `d884169` and tmark `b866eb4`.

## Size, against `master`

| | master | branch |
| - | -----: | -----: |
| `src/texsmith`, Python lines | 43 018 | 39 917 |
| tests (`tests/` + `packages/`) | 18 422 | 19 871 |
| tests collected | 1 017 | 1 359 |
| runtime dependencies | 24 | 22 |
| largest module | `snippet.py`, 1 768 | `snippet.py`, 1 723 |

The diff is 990 files, +93 325 / −24 925. The insertions are mostly the
committed regression baseline (3.1 MB of `.tex`/`.typ` under
`tests/parity/baseline/`, 248 entries), the design notes under `specs/`, and
the generated `src/texsmith/ir/model.py`. The production package is
**3 101 lines smaller** than on `master` while doing more, because the
Python-Markdown pipeline (17 extensions, two writers, the hand-written IR,
the legacy HTML reader, 45 Jinja partials) went and the TMark core took its
place: 37 309 lines of Rust in `tmark`, 321 tests, 102 conformance fixtures.

`markdown`, `pymdown-extensions` and `python-markdown-math` are gone;
`tmark` is the one addition.

## State

- TeXSmith: 1 359 tests pass, `ruff check` and `ruff format --check` clean.
- tmark: 321 tests, `clippy -D warnings` clean, `cargo fmt --check` clean,
  generated artifacts (schemas, registry tables) reproduce with no diff.
- Every example builds: 58/58 corpus entries, and the engine sweep is
  24/24 under Tectonic, LuaLaTeX and XeLaTeX plus 26/26 under Typst.
- The documentation site builds with its PDF export: 303 pages, 3.2 MB. The
  six `[?…]` markers left in it are the pages that *document* what an
  unresolved reference looks like.
- `scripts/parity.py baseline --check` (the CI gate): 196 identical,
  54 skipped, 0 differing.

## What a reviewer should look at

1. **The spec and the code were written together.** Challenges C27–C50 were
   decided and implemented in the same commits, by the same agents. An
   independent conformance pass over the spec sections they touched is the
   one review this work has not had.
2. **The writers were never diffed against the 0.6 output.** The parity
   harness compared readers while both existed; it now gates one rendering
   against a recorded baseline. `specs/migration/parity-triage.md` lists
   what the comparison found while it could still be made, and what stayed
   open.
3. **Two copies of `texsmith.typ`** — the shipping one under
   `src/texsmith/templates/common/` and the crate's reference under
   `crates/tmark-writers/assets/` — must define the same functions with the
   same signatures. Nothing generates one from the other.
4. **The `FRAGMENTS` contract spans both repositories.** A macro added on
   the tmark side fails `test_every_provides_entry_is_defined` here until
   the fragment defines it. That failure is the intended alarm, but it
   means a tmark release and a TeXSmith release are coupled.

## Refactoring the migration did not do

- `adapters/plugins/snippet.py` (1 723 lines) is the largest module and now
  mixes fence parsing, a nested conversion, a cache and an image grid. The
  pass calls into it; splitting it would let the pass own the IR half.
- `ui/cli/commands/render.py` (1 143 lines) grew three options and never
  lost any.
- `extensions/` survives for two files the HTML reader needs
  (`tables/schema.py`, `texlogos/specs.py`). The package name no longer
  says what it holds.
- `core/` is 13 041 lines across conversion, templates, fragments,
  bibliography and metadata; the pass framework took the rendering half out
  of it, and the rest would benefit from the same treatment.

## Before merging

- The five `ref: texsmith-migration` lines in `.github/workflows/ci.yml`
  point at the tmark branch. They become `main` when tmark merges — the two
  merges are ordered: tmark first, then this.
- `vendor/tmark` is a gitignored symlink locally and a checkout in CI. A
  release replaces it with the published wheel (`tmark>=0.X,<0.X+1`), which
  is what `specs/tmark-migration.md` D8 describes and nobody has done yet.
- The version is still `[Unreleased]` in `CHANGELOG.md`; releases here are
  cut in their own commit and tag.
