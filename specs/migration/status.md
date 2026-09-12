# Migration status (2026-09-11, end of wave 3)

Measured with `scripts/migrate_examples.py build-migr` (copy the example,
`tmark lint --fix` its sources, `texsmith --reader tmark … --build`), on
the parity corpus of `tests/parity/corpus.yml` (58 entries: 32 LaTeX, 26
Typst).

| Backend | Build through `--reader tmark` | Not built, why |
| ------- | ------------------------------ | -------------- |
| LaTeX | 31 / 32 | `emoji-color` needs `lualatex`, absent on this machine (also absent from the legacy baseline run) |
| Typst | 24 / 26 | `markdown`, `math`: `mitex` 0.2.6 rejects `\begin{aligned}` / `\imath` (pre-existing, see baseline.md); run from a `/home` directory (the snap `typst` cannot read `/tmp`) |

The `docs/` corpus (144 pages × 2 backends, minus the entries needing
Docker, network or nested builds) renders through the tmark reader without
an error (`scripts/parity.py render --reader tmark`).

What the tmark path still lacks before the flip (plan phase 4):

- the `snippet` pass (nested preview builds; the `snippet` example builds
  because the fences render as code blocks) and the retargeted `HtmlReader`
  (`.html` input, `press.reader: html` fallback) — both in progress;
- the MkDocs companion on `lower_web` (`examples/mkdocs`) — in progress;
- the parity triage: `scripts/parity.py diff` between the readers, the
  allow-list of intended differences (`\tsdivider`, contract macros instead
  of partials, zero-width collapse, script spans next to a backslash);
- done since: `ResolveOptions.lang` from the document language,
  `--numbering {backend,tmark}`, and `--deprecated {warning,info,off}` /
  `press.diagnostics.deprecated` as the transition knob for `--strict`;
  open on the tmark side: the writers do not yet use `lang` for the label
  words (`PREFIX_NAMES`).

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
