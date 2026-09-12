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

- the `snippet` pass (nested preview builds; the `snippet` example builds
  because the fences render as code blocks) and the retargeted `HtmlReader`
  (`.html` input, `press.reader: html` fallback) — both in progress;
- the MkDocs companion on `lower_web` (`examples/mkdocs`) — in progress;
- the parity triage is done and closed out (`parity-triage.md` §7): the
  cross-reader `scripts/parity.py diff` is retired as a gate and the harness
  now guards the tmark path instead — see "What the harness measures now";
- done since: `ResolveOptions.lang` from the document language,
  `--numbering {backend,tmark}`, and `--deprecated {warning,info,off}` /
  `press.diagnostics.deprecated` as the transition knob for `--strict`;
  open on the tmark side: the writers do not yet use `lang` for the label
  words (`PREFIX_NAMES`).
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

- the MkDocs companion on `lower_web` (`examples/mkdocs` builds, its plugin
  configuration untouched by this task);
- docs task 5.3: `docs/syntax/*`, `docs/guide/plumbing/pipeline.md`,
  `AGENT.md` and the `writing-texsmith` skill still teach the legacy
  spellings.

## What the harness measures now

`scripts/parity.py` no longer measures the migration. The cross-reader
comparison it was built for is retired: `examples/**` and `docs/**` are
canonical TMark, which the legacy `html` reader cannot parse, and `--reader`
defaults to `tmark`, so diffing the two readers over the corpus reports noise.
What the harness is now is a **regression gate on the tmark path**.
`parity.py baseline` renders every corpus entry with the default reader,
normalises it and writes `tests/parity/baseline/<id>/<stem>.{tex,typ}`, which is
committed; `baseline --check` re-renders and fails on any difference, with no
allow-list in the way — both sides come from the same reader, so a change is
either a regression or something an author re-records in a diff a reviewer
reads. That is what the `parity` job of `ci.yml` runs on every PR (`--without
docker --without tectonic --without network`, the same set the record was made
with, so those entries are skipped and keep their record). The nightly
`parity-pdf` workflow adds `parity.py pdf --baseline --check`: it rebuilds
`abbr`, `counters`, `index` and `marginnote` through tectonic and compares each
page's text layer, raster size and ink coverage against
`tests/parity/pdf-baseline.json` — so the nightly guards the rendering rather
than the migration. `parity.py diff` and `tests/parity/allow.yml` survive,
migration-only: `diff` refuses to run without an explicit `--only` entry set and
its `--help` says it is there to audit a document that has not been migrated
yet. The findings the allow-list encodes are closed out in `parity-triage.md`.

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
