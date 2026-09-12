# Baseline — the examples before the migration (2026-09-11)

Clean rebuild of every example of `examples/Makefile` (except `mkdocs`,
whose output path is fixed by `mkdocs.yml`) with the current pipeline on
the `tmark-migration` branch, into `build-baseline/` of each example:

```sh
for d in …; do make -C examples/$d OUTPUT_ROOT=build-baseline ENGINE=tectonic all; done
```

| Backend | Result |
| ------- | ------ |
| LaTeX (tectonic) | 23 / 23 examples build a PDF |
| Typst | 21 / 23 build; `markdown` and `math` fail inside `mitex` 0.2.6 (`unknown variable: diff`, `unknown symbol modifier`) on `\begin{aligned}` math. Pre-existing, not a migration regression. |

The `.tex` / `.typ` files under `build-baseline/` are the raw legacy outputs.
The parity harness (plan §4, task 4.1; design in `writers-and-passes.md` §5)
keeps its own, *normalised* copy under `tests/parity/baseline/<id>/`, one
directory per entry of `tests/parity/corpus.yml` (every example command line
and every `docs/**/*.md` page, both backends). That copy **is committed**:

```sh
uv run python scripts/parity.py baseline          # re-render the tmark reader and rewrite it
uv run python scripts/parity.py baseline --check  # what CI runs on every PR: exit 1 on drift
uv run python scripts/parity.py list              # entries, requirements, what can run here
```

Since the flip that copy records the **tmark** reader — the CLI default — so it
is a regression gate on the shipped path, not a memory of the legacy one
(`writers-and-passes.md` §5).

Entries whose toolchain is missing (`requires:` in the corpus — a diagram
renderer, network for remote assets, a LaTeX engine for nested snippet
builds) are reported as *skipped*, never as passed; the PR job skips the
diagram and snippet entries on purpose, the nightly `parity-pdf` workflow
runs everything and the PDF pixel diff.

Goal of the whole migration, restated: the same 23 (+ `mkdocs`) examples
build again, from sources rewritten in canonical TMark, through the tmark
reader and writers.
