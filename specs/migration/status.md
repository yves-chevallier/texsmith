# Migration status (2026-09-11, end of wave 3)

Measured with `scripts/migrate_examples.py build-migr` (copy the example,
`tmark lint --fix` its sources, `texsmith --reader tmark … --build`), on
the parity corpus of `tests/parity/corpus.yml` (58 entries: 32 LaTeX, 26
Typst).

| Backend | Build through `--reader tmark` | Not built, why |
| ------- | ------------------------------ | -------------- |
| LaTeX | 31 / 32 | `emoji-color` needs `lualatex`, absent on this machine (also absent from the legacy baseline run) |
| Typst | 20 / 26 | `book`, `paper`: `.bib` not reaching `#bibliography` on the Typst path (in progress); `markdown`, `math`: `mitex` 0.2.6 rejects `\begin{aligned}` / `\imath` (pre-existing, see baseline.md); `diagrams`, `mermaid`: verified separately from a `/home` directory (the snap `typst` cannot read `/tmp`) |

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
- `ResolveOptions.lang` / `numbering` from the CLI, `--strict` semantics
  for the `deprecated` warnings the examples still carry before their
  sources are rewritten.
