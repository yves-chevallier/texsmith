# Migration status (2026-09-12)

Measured with `scripts/migrate_examples.py build-migr`: copy each entry of
the parity corpus (`tests/parity/corpus.yml`), rewrite its sources with
`tmark lint --fix`, build it with the CLI. The sources under `examples/`
are already in canonical TMark, so the fixer is a no-op on them and the
build is the real measurement.

| Backend | Builds | Not built |
| ------- | ------ | --------- |
| LaTeX | 31 / 32 | `emoji-color` asks for `lualatex`, which this machine does not have (the legacy baseline could not build it either) |
| Typst | 26 / 26 | — |

57 of the 58 corpus entries. The `docs/` corpus (128 pages × both
backends) renders through the same path, and the documentation site
builds with its PDF export (`TEXSMITH_BUILD=1 mkdocs build`).

## What the harness measures now

`scripts/parity.py` was built to diff the legacy reader against the tmark
reader on the same sources. That comparison ended with the flip: the
sources are canonical TMark, which the legacy reader cannot parse. The
harness now records and checks a baseline of the **tmark** path, so a
change to the parser, the writers or a pass shows up as a reviewable diff
in `tests/parity/baseline/`.

`parity.py baseline` renders every corpus entry with the default reader,
normalises it and writes `tests/parity/baseline/<id>/<stem>.{tex,typ}`, which
is committed; `baseline --check` re-renders and fails on any difference, with
no allow-list in the way — both sides come from the same reader, so a change
is either a regression or something an author re-records in a diff a reviewer
reads. That is what the `parity` job of `ci.yml` runs on every PR, with
`--without docker --without tectonic --without network`: the same set the
record was made with, so those entries are skipped and keep their record. The
nightly `parity-pdf` workflow adds `parity.py pdf --baseline --check`, which
rebuilds `abbr`, `counters`, `index` and `marginnote` through tectonic and
compares each page's text layer, raster size and ink coverage against
`tests/parity/pdf-baseline.json` — page bitmaps are not hashed, because
tectonic's TeX bundle, the downloaded fonts and pymupdf's antialiasing are
none of them pinned. So the nightly guards the rendering rather than the
migration.

`parity.py diff` and `tests/parity/allow.yml` survive, migration-only: `diff`
refuses to run without an explicit `--only` entry set, it loads the allow-list
leniently (an entry past its expiry is a warning, not a failed load), and its
`--help` says it is there to audit a document that has not been migrated yet.
The findings the allow-list encodes are closed out in `parity-triage.md` §7.

## Known duplication

`src/texsmith/templates/common/texsmith.typ` (what ships, and what the
tmark Typst path imports) and `crates/tmark-writers/assets/texsmith.typ`
(what the Rust writers are written against, exposed as
`tmark_writers::TEXSMITH_TYP`) are two copies of the same contract.
TeXSmith's copy is a superset: it adds the functions of the fragments the
writers do not name themselves (`ts-progress`, `ts-logo`, `ts-mark`,
`ts-codeinline`, the critic four, `ts-icon`). Every function the writers
call must exist in both, with the same signature. Until one generates the
other, a change to either is a change to both;
`tests/test_fragment_contracts.py` checks TeXSmith's copy against what
`tmark.fragments()` declares, not against the crate's file.

The same hazard applies to the `FRAGMENTS` table itself: a contract macro
added on the tmark side fails `test_every_provides_entry_is_defined` here
until the fragment defines it. That failure is the intended alarm.

## Open

- `Document.from_markdown(reader=…)` still defaults to the legacy reader
  while `ConversionRequest.reader` defaults to `tmark`; a library caller
  that omits it silently gets the other pipeline (it cost the snippet
  previews a build). The default moves with the deletion of the legacy
  path, which rewrites the tests that assert its output.
- The findings of `parity-triage.md` that remain open are listed there.
