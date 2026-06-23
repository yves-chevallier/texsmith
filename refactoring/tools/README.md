# Golden harness — `snapshot.py`

> Phase 0 safety net for the IR migration. Captures the LaTeX that TeXSmith
> produces **today** for every example / snippet / MkDocs page, and provides a
> normalised, reproducible `diff` against a committed baseline. A zero diff
> before/after a migration step is the proof of iso-rendering — the examples are
> the source of truth for the rendered output.

## What it does

For every case it runs the **same CLI command as the example's `Makefile`** but
**without** `--build` and `--engine`, so no PDF is compiled. Only the
deterministic text artefacts are captured:

- `*.tex` — the main document, fragments, and per-page documents (MkDocs).
- `*.sty` — generated style packages (`ts-fonts`, `ts-callouts`, `ts-code`, …).

Everything else is deliberately ignored: PDFs (non-deterministic, need a TeX
toolchain), PNG/JPG/binary assets, downloaded fonts (`fonts/`), `.aux`, `.log`,
`.latexmkrc`, and JSON manifests. The `.tex` is deterministic; the PDF is not.

Each captured artefact is **normalised** (see below) and written under
`refactoring/baseline/<case>/<relative-path>`.

## Usage

Run it through `uv` so the project (and the Docker helper) import cleanly:

```bash
uv run python refactoring/tools/snapshot.py list      # list cases + docker status
uv run python refactoring/tools/snapshot.py capture   # (re)write the baseline
uv run python refactoring/tools/snapshot.py diff       # compare to baseline; exit≠0 on drift
```

Targeting:

```bash
# Only specific cases (by case name OR example directory):
uv run python refactoring/tools/snapshot.py diff --only paper math letter-din

# Skip Docker-dependent cases even if Docker is present:
uv run python refactoring/tools/snapshot.py diff --skip-docker
```

`diff` prints a precise unified diff per drifted file (case, file, lines,
expected vs. obtained) and exits non-zero if **any** case drifted or failed to
render. `capture` overwrites the baseline for the captured cases and exits
non-zero only if a case failed to render.

> The plain `python refactoring/tools/snapshot.py …` form also works; it falls
> back to `python -m texsmith` / `python -m mkdocs` and probes `docker info`
> directly when TeXSmith is not importable in that interpreter.

## Coverage

26 cases, derived 1:1 from `examples/*/Makefile`:

| Case(s) | Source | CLI args (minus `--build`/`--engine`) | Docker |
|---|---|---|---|
| `abbr` | `abbr/abbreviations.md` | `-tarticle` | no |
| `admonition` | `admonition/admonition.md` | `-tarticle -acallouts.style=fancy` | no |
| `booby` | `booby/booby.md` | `-tarticle` | no |
| `book` | `book/book.md book.bib` | `-tbook -abibliography_style=numeric` | no |
| `code-block` | `code/code-block.md` | _(no template → fragment)_ | no |
| `code-inline` | `code/code-inline.md` | _(no template → fragment)_ | no |
| `colorful` | `colorful/colorful.md` | _(no template → fragment)_ | no |
| `diagrams` | `diagrams/diagrams.md` | `-tarticle` | **yes** |
| `dialects` | `dialects/dialects.md` | `-tarticle` | no |
| `emoji-default` | `emoji/emoji.md` | `-tarticle` | no |
| `emoji-bw` | `emoji/emoji.md` | `-tarticle -afonts.emoji=black` | no |
| `fonts` | `fonts/fonts.md` | `-tarticle` | no |
| `index` | `index/index.md` | `-tarticle` | no |
| `letter-din` | `letter/letter.md` | `-tletter -aformat=din` | no |
| `letter-sn` | `letter/letter.md` | `-tletter -aformat=sn` | no |
| `letter-nf` | `letter/letter.md` | `-tletter -aformat=nf` | no |
| `marginnote` | `marginnote/marginnote.md` | `-tarticle` | no |
| `markdown` | `markdown/features.md` | `-tarticle` | no |
| `math` | `math/math.md` | `-tarticle -apress.override.preamble=\usepackage{csquotes}` | no |
| `mermaid` | `mermaid/mermaid.md` | `-tarticle` | **yes** |
| `multi-document` | `multi-document/a.md b.md c.md config.yml` | `-tarticle` | no |
| `paper` | `paper/cheese.md cheese.bib` | `-tarticle` | no |
| `progressbar` | `progressbar/progressbar.md` | `-tarticle -apress.override.preamble=\usepackage{progressbar}` | no |
| `recipe` | `recipe/cake.yml` | `-t.` (local template in cwd) | no |
| `snippet` | `snippet/docs/index.md` | `-tarticle` | no |
| `mkdocs` | `mkdocs/` | `mkdocs build` (no `TEXSMITH_BUILD`) → `press/**` | no¹ |

¹ The `mkdocs` example does not currently exercise diagram conversion, so its
build does not need Docker. If diagram pages are added it should be re-marked.

### Deliberately not covered

- **PDF output / `make all`.** Out of scope by design: PDFs are
  non-deterministic and require a TeX engine. The harness only proves the `.tex`
  is stable.
- **`examples/paper/mkdocs.yml`.** Despite the Phase 0 brief, this config has
  **no** `texsmith` MkDocs plugin (it is a plain Material site) and therefore
  produces no `.tex`. The `paper` content is covered via the `paper` CLI case
  (`cheese.md`). Only `examples/mkdocs/mkdocs.yml` wires the plugin.
- **The `emoji` `color` variant.** It exists only for `lualatex` PDF builds; its
  `.tex` is the same shape as the other emoji variants, so it is not a distinct
  text case. `emoji-default` and `emoji-bw` cover the `.tex` paths.
- **Downloaded fonts (`fonts/*.otf|ttf`).** Binary, not text.

### Docker-dependent cases (`requires-docker`)

`diagrams` and `mermaid` need a diagram backend. The pipeline auto-selects
playwright → cairosvg → Docker; in CI without those, Docker is the fallback.
The harness checks Docker via the project helper
`texsmith.adapters.docker.is_docker_available`. When Docker is unavailable, or
`--skip-docker` is passed, these cases are **skipped (not failed)** and reported
in the summary as reduced coverage:

```
=== diff summary ===
  captured: 24
  skipped : 2
  failed  : 0
    - SKIP diagrams: requires-docker (Docker unavailable or --skip-docker)
    - SKIP mermaid: requires-docker (Docker unavailable or --skip-docker)
```

The baselines for `diagrams`/`mermaid` were captured **with** Docker present.
When Docker is later available, `diff` compares against them; when absent they
are simply skipped, so the GATE is never blocked by a missing Docker daemon.

## Sources of non-determinism & how they are neutralised

All normalisation lives in `NORMALISATION_RULES` in `snapshot.py` as a list of
documented regex substitutions, applied (in order, after absolute-path
substitution) to every captured artefact **before** it is written or compared.
Two runs over unchanged code therefore yield byte-identical normalised output —
verified by running `diff` twice and getting an empty result both times.

| Source | Where it comes from | Neutralised by | Placeholder |
|---|---|---|---|
| `\today` | TeX expands it to the build date | `latex-today` | `<DATE>` |
| English long date (`March 15, 2025`) | `core/document_date.py` for `date: today`/ISO dates | `english-long-date` | `<DATE>` |
| French long date (`5 mars 2026`, `1er mars 2026`) | same, French locale | `french-long-date` | `<DATE>` |
| ISO 8601 timestamps | e.g. remote-asset manifests (`checked_at`) | `iso-timestamp` | `<TIMESTAMP>` |
| Git versions (`v0.3.1-5-gabc-dirty`, `v1.2.3`) | `version: git` → `git describe --tags --dirty` (`core/git_version.py`) | `git-describe-version` | `<GITVERSION>` |
| Content-addressed asset names `<name>-<sha>.<ext>` | snippet renders, converted assets | `asset-hash-filename` | `<name>-<HASH>.<ext>` |
| Bare content hashes `<sha64>.<ext>` | converted-asset filenames | `bare-hash-filename` | `<HASH>.<ext>` |
| Absolute paths (`$REPO`, `$HOME`, `$TMPDIR`) | output dir / cache leakage | code (`_normalise_absolute_paths`) | `<REPO>` / `<HOME>` / `<TMP>` |

Notes:

- **Asset hashes are normalised on purpose.** They are content-addressed and
  *currently* stable, but they derive from the rendered asset (e.g. a snippet
  PDF), whose bytes could shift during the migration without the document
  semantics changing. The `.tex` still proves the reference is emitted at the
  right place; semantic drift in the document shows up elsewhere in the `.tex`.
- **Front-matter literal dates are not normalised.** `book/book.md` carries
  `date: 2025-03-15`, rendered into a `\newcommand{\bookdate}{2025-03-15}` — a
  fixed document value, not a build-time date, so it stays verbatim.
- **No example currently uses `date: today` or `version: git`**, so those rules
  are dormant on the present baseline. They are in place as forward protection:
  if a future example opts in, the harness stays deterministic.
- The `markdown` example fetches a random image from `picsum.photos`. The random
  bytes only affect a binary asset (referenced by a stable filename); the `.tex`
  and `.sty` are unaffected and deterministic across runs.

## How the baseline is stored

`refactoring/baseline/<case>/` mirrors the output directory layout (POSIX
relative paths), holding only the normalised `.tex`/`.sty`. It is committed and
is the reference every later phase diffs against.
