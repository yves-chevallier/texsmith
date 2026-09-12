# Decisions taken across the design notes (2026-09-11)

The five notes under this directory were written independently. Where they
disagree or leave a choice open, this file settles it. A note that says
otherwise is superseded by the line below; the notes are not rewritten.

| # | Question | Decision | Why |
| - | -------- | -------- | --- |
| X1 | `Header.level`: does the slot offset/base level get written into the IR (`writers-and-passes.md` §3 row 3) or passed as a writer option (`python-ir-and-passes.md` §4)? | **Writer option.** `WriterOptions.headings { base_level, numbered }` per slot body; `Header.level` stays the author's. Order: `title` promotion runs before `resolve` (it removes a block); `resolve` once on the whole document; `slots` after `resolve`; the per-body options are computed from the body's heading levels at `write` time. | The IR keeps round-tripping and the source map stays exact; tmark T6 is a small addition. |
| X2 | `---` (`HorizontalRule`): `\clearpage` in the writer or a `\tsdivider` contract? | **`\tsdivider`** provided by `ts-typesetting` (default `\clearpage`), from the first Rust line. The parity allow-list carries a `rewrite` entry. Amended 2026-09-12 (tmark challenge C48): only at the *top level* of the document. Inside a container the writers emit a second contract, `\tsrule` / `#ts-rule()` / `<hr class="rule">` — a separator that never breaks the page, because a page break there tears the container in two and Typst refuses it outright ("pagebreaks are not allowed inside of containers", which killed `markdown@typst`). | One migration, not two; a paged template restyles it without touching the writer. |
| X3 | Pygments `highlight` pass output: the whole `tscode` environment as one `RawBlock` (`fragment-contracts.md` §5) or `Div{name=code, attrs, content=[RawBlock payload]}` (`writers-and-passes.md` §3 row 12)? | **`Div{name=code}` + `RawBlock` payload.** The writer serialises the `tscode` keys (plus `engine=pygments`) exactly as for a `CodeBlock`; Python produces only the highlighted body. Inline: `RawInline` as both notes say. | The option serialisation exists once, in Rust; the `Div` keeps id and span for the source map. |
| X4 | Contract macro names and which constructs are contracts (the two notes differ on aside, keys, index, highlight, progress bar, scripts). | **`fragment-contracts.md` §1 and §3 are the reference for names and for the contract/structural split**; `writers-and-passes.md` §2 stays the reference for the LaTeX *behaviour* each construct must reproduce. Concretely: `\tsaside`, `\tskeys`, `\tsindex`, `\tsmark`, `\tsprogress[thin]{0.45}{label}`, `\tsscript{slug}{…}`, `\tsemoji`, `\tslead`, `\tsepigraph`, `tsdiv`, `tscallout`, `tscode`/`\tscodeinline`, `\tsdivider`; `\cite`, `\enquote`, `displayquote`, lists, headings, `figure`, tables, `\footnote`, `\href`, `\label`/`\hyperref` structural. | One note owns naming; the fragment note applied one convention to all 55 partials. |
| X5 | Is a Python `glossary` pass needed? | **Yes, after verification (2026-09-12).** The original answer was "verify first, no pass by default", with `examples/glossary` and `examples/abbr` as the test: they failed (parity triage F2), which is this decision's own condition for adding one. `press.declare.glossary` is a *flat* `term → definition` mapping to tmark, so TeXSmith's structured section turned `style`/`groups`/`entries` into glossary terms and declared none of the acronyms under `entries`; `abbr::keys` reads `Document.abbreviations` and `declare.acronyms` only, so no occurrence was substituted either. `passes/glossary.py` appends one `AbbrDef` per entry (the IR twin of `append_synthetic_abbr_lines`) and leaves `declare.glossary` holding only the flat terms it did not consume. | The fragment generates the *tables*, but the substitution needs the definitions in the IR before `write`. |
| X6 | Node ids: make them dense (tmark) or weaken the doc? | **Weaken `03-ir.md` §Identity to "unique per file".** TeXSmith relies only on "every id is below the allocator floor". | No code change for a property nothing needs. |
| X7 | `[^key]` / `^[k1,k2]` citations: M5 "or never" (tmark registry notes) vs the examples audit (book ×83, paper ×6, docs and skill teach it). | **Tokenizer rule now, in the first tmark wave**: a `[^key]` without a definition and a `^[…]` group lower to `Ref` (bracketed) with a `deprecated` fix to `@key` / `@[k1; k2]`; `^[` never opens a caret superscript. | The most frequent breaking change in real documents; without it no mechanical migration exists. |
| X8 | `Profile::Mkdocs` and `lower_web`: Rust or a Python splicer? | **Rust**, as `web-profile.md` recommends; the Python splicer is the fallback only if tmark's release cadence blocks phase 3.9. | The LSP preview and Zensical reuse it; escaping lives once. |
| X9 | Table model (R6): validate in Python until tmark does, or fix tmark first? | **tmark first, in the first wave**: the five rejected `tables.md` shapes, `table:` settings, `width-group`, nested per-group cells, printer round-trip or refusal (never flatten). Validation diagnostics in `tmark-lint` in the same wave. | The printer currently loses data silently, which violates the spec's round-trip rule; a Python validator would not fix that. |
| X10 | Diagnostics column: bytes or characters? | **Bytes, 1-based, on both sides** (today's `tmark-cli` convention). Revisit when an editor complains; change both or neither. | Identical lines from both tools; the LSP uses UTF-16 positions anyway. |
| X11 | Slot selectors matching a heading nested in a container (bs4 did). | **Top-level headings only**, warning `slot-nested-heading`. Re-examined on the corpus before the flip. | Sections are top-level by definition in the IR. |
| X12 | `inline_breaks` in two places (`WriterOptions.code.inline_breaks` for `\tscodeinline`, the pass for pygments/minted inline). | **Accepted**; both read `code.inline.breaks`. | Each side breaks the text it owns. |

## Waves

The implementation is organised in waves of parallel agents, one worktree
each. Wave 1 starts from these decisions:

- tmark `fixes`: examples-migration items 1–6, 8, 9 (`lint --fix --stdout`,
  citations X7, `///` fix, info-string attribute lists, string author,
  C20 fixes, silence → diagnostics).
- tmark `tables`: X9.
- tmark `registry`: `FRAGMENTS`, `KEY_LABELS`, `Profile::Mkdocs` spelling table, `edit_many`.
- tmark `writers`: `tmark-writers` common + escape + HTML writer, then the LaTeX writer in the order of `writers-and-passes.md` §6.
- tmark `py`: `tmark-py` (PyO3 + maturin): `parse`, `parse_with`, `format`, `lint`, `fixes`, `resolve` (dict), `schema`, `schema_hash`, `fragments`; `write` when the writers land.
- TeXSmith `parity`: `scripts/parity.py`, `tests/parity/corpus.yml`, committed baseline, CI job.
- TeXSmith `models`: `scripts/gen_ir_models.py`, `texsmith/ir/model.py`, `codec.py`, `walk.py`, tests.
- TeXSmith `diagnostics`: `texsmith/diagnostics/{model,codes,sink}.py`, `FileTable`, `format_diagnostic`, CLI rendering, `--strict`, `--diagnostics-json`.
- TeXSmith `captions` (running): task 0.1.

## Closing note — what shipped

All twelve decisions are implemented, and two were amended on contact with the
corpus rather than overturned.

- **X2** gained a second contract. `\tsdivider` = `\clearpage` is right at the
  top level and wrong inside a container, where it tears a box in two and Typst
  refuses it outright; the writers now pick `\tsrule` / `#ts-rule()` by their
  own nesting (tmark challenge C48, commit `604dac2`).
- **X5** was answered *yes*. Its own condition — `examples/glossary` and
  `examples/abbr` failing — was met (parity triage F2), so `passes/glossary.py`
  exists and appends one `AbbrDef` per front-matter entry.

X1 (a writer option, not `Header.level`), X3 (`Div{name=code}` plus a
`RawBlock` payload), X4 (`fragment-contracts.md` owns the macro names), X6
("unique per file"), X7 (the citation tokenizer rule, which is what made a
mechanical migration possible at all), X8 (`lower_web` in Rust), X9 (the table
model fixed in tmark first), X10 (byte columns on both sides), X11 (top-level
headings only) and X12 (`code.inline.breaks` read in both places) shipped as
written.

The waves all landed; what remains open is recorded per note, and the findings
that outlived the migration are in `parity-triage.md` §7.
