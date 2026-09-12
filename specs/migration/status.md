# Migration status (2026-09-12, after the flip — plan task 4.3)

Every `.md` under `examples/` is written in canonical TMark, in place, and
`--reader` defaults to `tmark`. Two measurements, both on the committed
sources (no scratch copies, no `lint --fix` at build time):

**The parity corpus** (`tests/parity/corpus.yml`, 58 entries: 32 LaTeX, 26
Typst), with `scripts/migrate_examples.py build-migr`:

| Backend | Builds through the tmark reader | Not built, why |
| ------- | ------------------------------- | -------------- |
| LaTeX | 31 / 32 | `emoji-color` needs `lualatex`, absent on this machine (also absent from the legacy baseline run) |
| Typst | 24 / 26 | `markdown`, `math`: `mitex` 0.2.6 rejects `\begin{aligned}` / `\imath` (pre-existing, see `baseline.md`); run from a `/home` directory (the snap `typst` cannot read `/tmp`) |

**The Makefiles**, one `make -C examples/<name> all` per example, both
backends, `ARTIFACTS_DIR` set so a missing PDF fails the target: **25 / 27**
(the 24 of `examples/Makefile` plus `counters`, `glossary` and `tables`, which
have Makefiles but are absent from its `EXAMPLES` list). The two misses are
the Typst halves of `markdown` and `math` above; both build their LaTeX PDF.
`custom-render` has no Markdown source and no PDF target.

`tmark check --strict` over the rewritten sources: no warning, no error,
except the five `table-*` errors of `tables.md`, which are the deliberate
mistakes of its "Error cases" section. What is left is hints and one info,
listed with a reason each in `examples-flip.md` §3.

The `docs/` corpus (144 pages × 2 backends, minus the entries needing Docker,
network or nested builds) renders through the tmark reader without an error
(`scripts/parity.py render --reader tmark`).

## What the flip closed, and what it did not

Closed by task 4.3 (details in `examples-flip.md`, closing section of
`examples-migration.md`):

- the example sources, the `--reader` default, `docs/cli/index.md` and the
  changelog entry;
- `press.declare.glossary` read where `glossary:` was, and its entries
  reaching the body again as synthesised abbreviation definitions (decision
  X5's trigger was exactly `examples/glossary`).

Still open before 0.7.0:

- **`tests/parity/baseline/` is now stale, and cannot simply be re-recorded.**
  It holds the *legacy-reader* render of each corpus entry, keyed on sources
  this task rewrote; the legacy reader does not understand the canonical
  spellings, so re-recording it would freeze the wrong output (`{.thin}` and
  `{raw latex}(…)` come out as literal text — `examples-flip.md` F8).
  `scripts/parity.py baseline --check` reports drift on every rewritten
  example. Whether the harness keeps a pre-flip copy of the sources, compares
  only the entries that did not change spelling, or drops the legacy side
  altogether is the parity triage's call.
- the parity diff itself (`scripts/parity.py diff` between the readers) and
  its allow-list of intended differences;
- the MkDocs companion on `lower_web` (`examples/mkdocs` builds, its plugin
  configuration untouched by this task);
- docs task 5.3: `docs/syntax/*`, `docs/guide/plumbing/pipeline.md`,
  `AGENT.md` and the `writing-texsmith` skill still teach the legacy
  spellings.

## Known duplication

`src/texsmith/templates/common/texsmith.typ` (what ships, and what the tmark
Typst path imports) and `crates/tmark-writers/assets/texsmith.typ` (what the
Rust writers are written against, exposed as `tmark_writers::TEXSMITH_TYP`)
are two copies of the same contract. TeXSmith's copy is a superset: it adds
the functions of the fragments the writers do not name themselves
(`ts-progress`, `ts-logo`, `ts-mark`, `ts-codeinline`, the critic four,
`ts-icon`). Every function the writers call must exist in both, with the same
signature. Until one generates the other, a change to either is a change to
both; `tests/test_fragment_contracts.py` checks TeXSmith's copy against what
`tmark.fragments()` declares, not against the crate's file.
