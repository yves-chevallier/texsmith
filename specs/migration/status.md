# Migration status (2026-09-12)

Measured (2026-09-12, with a script since deleted) by copying each entry of
the parity corpus (`tests/parity/corpus.yml`), rewrite its sources with
`tmark lint --fix`, build it with the CLI. The sources under `examples/`
are already in canonical TMark, so the fixer is a no-op on them and the
build is the real measurement.

| Backend | Builds |
| ------- | ------ |
| LaTeX | 32 / 32 |
| Typst | 26 / 26 |

Every entry of the corpus, with TeX Live 2025 and its `lualatex` on the
machine (`emoji-color` is the one entry that asks for it). The `docs/` corpus (128 pages × both
backends) renders through the same path, and the documentation site
builds with its PDF export (`TEXSMITH_BUILD=1 mkdocs build`).

## What the harness measures now

`scripts/parity.py` was built to diff the legacy reader against the tmark
reader on the same sources. That comparison ended with the flip, and the
legacy reader itself went with phase 5: a Markdown source has exactly one
reader and the CLI has no `--reader` option. The harness now records and
checks a baseline of that one rendering, so a change to the parser, the
writers or a pass shows up as a reviewable diff in `tests/parity/baseline/`.

`parity.py baseline` renders every corpus entry, normalises it and writes
`tests/parity/baseline/<id>/<stem>.{tex,typ}`, which is committed;
`baseline --check` re-renders and fails on any difference, with no allow-list
in the way — both sides are the same rendering of the same source, so a change
is either a regression or something an author re-records in a diff a reviewer
reads. That is what the `parity` job of `ci.yml` runs on every PR, with
`--without docker --without tectonic --without network`: the same set the
record was made with, so those entries are skipped and keep their record. The
nightly `parity-pdf` workflow adds `parity.py pdf --baseline --check`, which
rebuilds `abbr`, `counters`, `index` and `marginnote` through tectonic and
compares each page's text layer, raster size and ink coverage against
`tests/parity/pdf-baseline.json` — page bitmaps are not hashed, because
tectonic's TeX bundle, the downloaded fonts and pymupdf's antialiasing are
none of them pinned.

What is left of the harness is `list`, `baseline [--check]`, `render --out`,
`pdf --baseline [--check]` and `seed-cache`. The cross-reader `diff`
subcommand and its allow-list (`tests/parity/allow.yml`, 86 entries) are
deleted: they compared two readers, and only one is left. What they recorded
about the migration is written up in `parity-triage.md`, which stays as the
history of what changed and why.

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

- `Document.from_markdown` has no `reader` parameter any more, and neither has
  `ConversionRequest`: a Markdown source has exactly one reader. The hazard
  this entry recorded — a library caller silently getting the other pipeline,
  which cost the snippet previews a build twice — is closed by deletion rather
  than by a changed default.
- The findings of `parity-triage.md` that remain open are listed there.
