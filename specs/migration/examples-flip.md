# The flip — examples in canonical TMark, `tmark` the default reader

Plan §4, task 4.3. Companion of `examples-migration.md` (the inventory taken
*before* the rewrite) and of `baseline.md` (what built before any change).
This file records what the flip changed, what it found and what it left.

## 1. What was done

1. Every `.md` under `examples/` (`README.md` included) was rewritten in
   place: `tmark lint --fix` first, then the constructs the fixer does not
   spell for you, reviewed diff by diff. The completion criterion is
   `tmark check --strict FILE` at zero warnings and errors; §3 lists the
   hints deliberately kept.
2. `--reader` defaults to `tmark`. `--reader html` stays for one release and
   an `.html` input is unaffected (`ConversionService` dispatches on the input
   kind, never on `request.reader`).
3. `uv run make -C examples all`, every example, both backends.

## 2. Build result (tectonic, Typst 0.13 / mitex 0.2.6)

One `make -C examples/<name> all` per example (LaTeX **and** Typst where the
example has a Typst target), `ARTIFACTS_DIR` set as the top-level Makefile
sets it, so a missing PDF fails the target.

`uv run make -C examples all` itself **halts** at `examples/markdown`'s Typst
PDF — its `all` recipe is a `set -e` shell loop, so `-k` does not carry it
past the failure and the ten examples after `markdown` in `EXAMPLES` are never
reached in one invocation. The failure is the mitex one of F2, pre-existing
and Typst-only; `markdown`'s own LaTeX PDF builds. Driving the examples one by
one (what the table below reports) is the way to see the whole picture until
mitex is fixed or `markdown.md` stops feeding it `\begin{aligned}`.

| Example | Builds | What changed in its source |
| ------- | ------ | -------------------------- |
| abbr | yes | nothing (already canonical) |
| admonition | yes | 17 `!!!` → `:::`; the seven types `:::` does not predeclare (`caution summary success failure bug quote`, custom `unicorn`) declared under `press.declare.admonitions`. The LaTeX is byte-identical to the `!!!` build. |
| booby | yes | nothing |
| book | yes | 91 `^[key]` / `^[k1,k2]` → `@key` / `@[k1; k2]` / `@doi:…`, 6 `/// caption` → a `Figure:` line after the image, `press.admonition_style` → `press.callouts.style` (inert either way: `admonition_style` was read by nothing in `src/`, and `book.md` has no callout) |
| code | yes | `` `#!c …` `` → `{code lang=c}[…]` (×2) |
| colorful | yes | nothing |
| counters (not in `examples/Makefile`) | yes | top-level `counters:` → `press.declare.counters`, 10 `#{p:k}` → `{counter}(p:k)` |
| diagrams | yes | `/// caption` → `Figure:` line; `` ```mermaid {width=80%} `` → `` ```mermaid image width="80%" `` |
| dialects | yes | nothing |
| emoji | yes | `/// latex` → a ```` ```latex raw ```` fence |
| fonts | yes | nothing |
| glossary (not in `examples/Makefile`) | yes | top-level `glossary:` → `press.declare.glossary` (and see finding F1) |
| index | yes | 2 `{latex}[…]` → `{raw latex}(…)`, 7 `#[term]` → `{index}[term]` |
| letter | yes | nothing |
| marginnote | yes | 8 `{margin}[…]{l\|r}` → `{aside side=…}[…]`, `{latex}[…]` → `{raw latex}(…)`; the list-item continuations the fixer flattened re-indented by hand (finding F3); prose and README updated to `{aside}` |
| markdown | **LaTeX yes, Typst no** (mitex, F2) | `=== "Tab"` → `:::: tabs` / `::: tab {title=…}`, `^^text^^` → `{underline}[text]`, `???+ note "Title"` → `::: note {title=… collapsed=false}`, `!!!`/`???` → `:::`, `/// latex` → a raw fence, `{latex}[…]` → `{raw latex}(…)`, `{: .thin}` → `{.thin}`, `--8<-- "hanoi.py"` in a fence → `include="hanoi.py"`, `mermaid { width=20% }` → `mermaid image width="20%"`, `-----` → `---`; the illustrative `md` fences updated to match |
| math | **LaTeX yes, Typst no** (mitex, F2) | nothing: the document exists to show that `\(…\)` and `$…$` are both accepted |
| mermaid | yes | `` ```mermaid `` → `` ```mermaid image `` |
| mkdocs | yes | **nothing** — its `docs/*.md` were already clean under `tmark check`, and its `!!!` callout and `{.snippet …}` fence are class E spellings MkDocs Material renders natively. Its plugin configuration is the MkDocs companion's, untouched here. |
| multi-document | yes | nothing |
| paper | yes | 6 `[^key]` → `@key`, 3–4 `/// figure-caption` / `/// table-caption` with their `attrs: {id: …}` line → a `Figure:` / `Table:` line carrying `{#id}`, top-level `bibliography:` → `press.sources.bibliography`, `[](#id)` → `@id` with the prose adjusted, `{ width=80% }` → `{width=80%}` |
| progressbar | yes | `{: .thin}` → `{.thin}` (×2) |
| recipe | yes | nothing (API example, no Markdown source) |
| snippet | yes | nothing |
| tables (not in `examples/Makefile`) | yes | nothing; its five `table-*` errors are the deliberate mistakes of its "Error cases" section |
| typst-article | yes | `\(…\)` → `$…$` |
| typst-hello | yes | nothing |

**25 / 27**, the two misses being the pre-existing mitex failures of
`baseline.md`, both Typst-only; their LaTeX PDFs build. `custom-render` has no
Markdown source (it drives the API from `counter.py`) and no PDF target.

`emoji-color` is a *corpus* entry (`emoji.md -afonts.emoji=color`), not a
Makefile target; it needs `lualatex`, absent here, as it was for the legacy
baseline.

## 3. Diagnostics deliberately kept

`tmark check --strict` over the rewritten corpus reports no warning and no
error except the five in `tables.md`. What is left:

| Code | Count | Where | Why it stays |
| ---- | ----- | ----- | ------------ |
| `position-word` | 16 | colorful, counters, dialects, features, marginnote, paper, tables | Hint. Most are false positives on ordinary prose ("below the yield point", "the table below" in a paragraph that is itself the table's introduction). Rewriting them with `@` would change what the sentences say. |
| `caption-id-off-convention` | 7 | paper | Hint. The ids (`melting-behavior`, `cheese-samples`, `mechanical-results`) are the paper's own and are cited as such; renaming them to `fig:` / `tbl:` would be an editorial change with no output difference. |
| `lead-promotion` | 1 | features | Info. The leading `**text**` of the *Bold* section is the section's subject; `{lead}[…]` would make the demo lie. |
| `table-row-width`, `table-span`, `table-column-unknown` | 5 | tables | Errors on purpose: the "Error cases" section of `tables.md` demonstrates what validation rejects, and the document renders each as an inline error callout. |

`ref-unresolved` appears on `book.md`, `paper/cheese.md` and
`paper/docs/cheese.md` only when `check` is run without the sibling `.bib`:
`tmark check book.md book.bib` and `tmark check cheese.md cheese.bib` are
clean. The twin under `paper/docs/` needed one addition — it cites
`WADHWANI20111713`, whose DOI is declared in the sibling `cheese.md` only, so
the declaration was copied into its own `press.sources.bibliography`.

## 4. Findings

### F1 — `press.declare.glossary` was invisible to TeXSmith (fixed)

Moving `examples/glossary`'s front matter to the canonical
`press.declare.glossary` produced a PDF with **no glossary at all**: no
`\newglossary*`, no `\newacronym`, style back to the `list` default, and every
acronym a plain word. Two causes, both fixed in this branch because decision
X5 names exactly this example as the trigger:

- `core/metadata.py` only ever knew a `glossary:` section; `press.declare.
  glossary` is now hoisted onto it during normalisation, so the
  `("glossary", "style") → glossary_style` alias and every downstream consumer
  see the canonical spelling. The old spelling keeps working.
- the entries never reached the *body*. The legacy path synthesised a
  `*[KEY]: description` line per entry for `markdown.abbr`; the tmark reader
  now appends the same lines to the source before `tmark.parse`, at the end
  where they move no existing span, so tmark lowers each occurrence to `Abbr`
  and the writers to `\tsacr{…}`.

Covered by `tests/test_front_matter_glossary.py` (three cases rewritten in the
canonical spelling, one kept on the deprecated one).

### F2 — `markdown` and `math` still fail inside mitex 0.2.6 (not fixed, not ours)

Unchanged from `baseline.md`: `\begin{aligned}` and `\imath` reach
`mitex` 0.2.6, which answers `unknown variable: diff` / `unknown symbol
modifier`. Pre-existing, independent of the reader.

```sh
uv run make -C examples/math ENGINE=tectonic all   # build/typst/math.pdf missing
```

### F3 — `tmark lint --fix` flattens a continuation line inside a list item

When the rewritten construct spans a line break inside a list item, the fixed
text loses the continuation's indentation. Minimal reproduction:

```md
- Quantum mechanics{margin}[non-commuting
  observables]{r} follows.
```

```console
$ tmark lint --fix --stdout repro.md
- Quantum mechanics{aside side=right}[non-commuting
observables] follows.
```

The list still parses (lazy continuation), so nothing breaks, but the source
becomes misleading. Re-indented by hand in `marginnote.md`. tmark side.

### F4 — a failed Typst compile does not fail the command

`texsmith … --format typst --build` prints `typst compile failed: …` and exits
**0** unless `--debug` is on
(`src/texsmith/ui/cli/commands/render.py`, `if not ok and debug_enabled()`).
A script cannot tell a compiled PDF from a failed one; `make -C examples all`
only notices because the artifact copy then finds no PDF.

```console
$ cd examples/math && uv run texsmith math.md -o out -tarticle --format typst --build
… typst compile failed: … unknown symbol modifier
$ echo $?
0
```

Pre-existing, unrelated to the reader. Not patched here: the branch exists so
that a machine without a Typst compiler degrades gracefully, and separating
"no compiler" from "the compiler said no" is a change with its own test.

### F5 — `:::` validates callout types, `!!!` does not

`!!! caution` parses with no diagnostic whatever the word; `::: caution` warns
`container-unknown` unless the type is declared. That is the intended
direction (P1, declare once), but it makes `!!!` → `:::` a two-step migration
for any document using Material's extra types. `admonition.md` now declares
`caution summary success failure bug quote unicorn` under
`press.declare.admonitions`, and the generated LaTeX is unchanged.

### F6 — `counters`, `glossary` and `tables` are absent from `examples/Makefile`

They have their own Makefiles and are entries of `tests/parity/corpus.yml`,
but `EXAMPLES` in `examples/Makefile` does not list them, so
`make -C examples all` never builds them. All three build; whether to add them
is a call for the Makefile's owner, so `EXAMPLES` is left as it was.

### F8 — the rewritten examples no longer build through `--reader html`

The canonical spellings are canonical for TMark, not for Python-Markdown, so a
rewritten source rendered by the legacy reader comes out wrong — silently,
because the legacy path has no diagnostic for a spelling it does not know. Two
measured cases, from `parity.py baseline --check`:

```diff
### progressbar/progressbar.tex
-{\progressbar[width=9cm,…]{0.75} Review}\par
+[=75\% \enquote{Review}]\{.candystripe\}

### index/index.tex
-\clearpage
+\{raw latex\}(\textbackslash{}clearpage)
```

`attr_list` wants `{: .x}`, and `{raw latex}(…)` is not the `{latex}[…]` the
legacy extension registers. This is expected and is the point of the flip, but
it fixes the meaning of the escape hatch: **`--reader html` is for a document
still written in the 0.6 spellings**, not a way to render a canonical one. The
docs and the changelog entry say so.

Its consequence is on the parity harness, not here: `tests/parity/baseline/`
holds the *legacy* render of every corpus entry, keyed on sources this task
rewrote, so `parity.py baseline --check` now reports drift on each rewritten
example. Re-recording the baseline — or freezing a pre-flip copy of the
sources for it — is the parity triage's call.

### F7 — `uv run pytest` with no path collects `vendor/tmark`

The `vendor/tmark` symlink the migration asks for is inside the repository and
has no `testpaths` guard, so a bare `uv run pytest` also collects
`vendor/tmark/crates/tmark-py/tests/`, which errors on fixtures that live in a
conftest pytest does not pick up from there (234 collection errors, none of
them TeXSmith's). `uv run pytest tests/` is clean. CI is unaffected: it has no
`vendor/` symlink. Left alone rather than adding `testpaths` under someone
else's feet.

## 5. What remains

- The sugar `tmark fmt` normalises but `tmark check` accepts is left as
  written where the document exists to demonstrate it: `~~del~~`, `==mark==`,
  `^sup^` / `~sub~`, `++Ctrl+C++`, `__smallcaps__`, `:smile:`, `\(…\)`,
  `!!!` in `examples/mkdocs`. Those files are therefore not fixed points of
  `tmark fmt --check`; `tmark check --strict` is the gate this branch drives
  to zero, not `fmt --check`.
- `examples/paper/docs/cheese.md` is the MkDocs-hosted twin of the paper and
  is not built by any Makefile; it was migrated for consistency (its
  `--8<--- "examples/paper/code.py"` became `include="../code.py"`, which is
  file-relative as tmark resolves it).
- `custom-render` still drives the API through a raw-HTML hook
  (`<span class="data-counter">`); rewriting it as an IR pass is
  examples-migration item TeXSmith-6, not part of the flip.
