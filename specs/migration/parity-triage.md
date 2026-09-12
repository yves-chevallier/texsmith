# Parity triage — legacy `html` reader vs the `tmark` reader

Phase 4.2 of the migration plan. Records what
`scripts/parity.py diff --reader-a html --reader-b tmark` reported over the
whole corpus, which differences were intended (and therefore carried by
`tests/parity/allow.yml` or by a normalisation rule), and which were bugs.

> **Historical.** The `html` reader, the `diff` subcommand and
> `tests/parity/allow.yml` have since been deleted; this file is what survives
> of them. See §7.

Run of 2026-09-12, on `tmark-migration` at `59ff0e8` merged into the triage
branch, with `vendor/tmark` linked to the local tmark checkout:

```
uv run python scripts/parity.py diff --reader-a html --reader-b tmark \
    --without docker --without tectonic --without network --jobs 4
```

## 1. Result

Document body (the gating table):

| status | entries |
| ------ | ------- |
| identical | 15 |
| allow-listed | 48 |
| differs (each with at least one finding below) | 129 |
| skipped (docker / tectonic / network) | 54 |
| **total** | **246** |

Of the 129 differing entries, 45 are LaTeX and 84 are Typst. The Typst count
is dominated by **F1**: 78 of the 84 lose the document title, so no Typst
entry can reach *allow-listed* before that one bug is fixed.

`tests/parity/allow.yml` now holds 86 entries (59 `rewrite`, 27 `hunk`), all
expiring at `0.8.0`. Every one of them fires at least once on this corpus —
a dead pattern is a pattern that stopped describing the difference it was
written for, so the triage checked for them and fixed or removed four.

The full-file (informative) table is 192 entries: 10 identical, 11
allow-listed, 171 differing — it additionally sees the preamble, where the
tmark path inlines `texsmith.typ` and a different fragment set.

### 1.1 After the TeXSmith-side round (2026-09-12)

The findings whose cause was in `src/texsmith/` are fixed — F1, F2, F7, F10,
F11's `uses_eqnref` item and the O5 decision behind F12 — each with its
commit named in §3. Measured with the tmark checkout of that afternoon (which
meanwhile grew the F3/F4/F5/F6 fixes, so both columns were re-measured on the
same one), body table over the whole offline corpus:

| status | before | after |
| ------ | ------ | ----- |
| identical | 18 | **35** |
| allow-listed | 54 | **85** |
| differs | 120 | **72** |
| skipped | 54 | 54 |
| **total** | **246** | **246** |

`--only 'docs/*'` alone (188 entries, 44 skipped), the scope that stays a
meaningful cross-reader diff after the examples flip: 7 → **23** identical,
37 → **62** allow-listed, 100 → **59** differing.

On the tmark checkout the triage itself used, the same fixes took the body
table from 15 / 47 / 130 to 32 / 76 / 84 (F1 alone: 15 / 47 / 130 → 32 / 73 /
87).

The PDF gate (§6) is clean: `abbr`, `counters`, `index` and `marginnote` are
all *identical* now that `\tsacr` is `\acrshort`.

No allow-list entry was made dead by these fixes; one entry was added
(`typst-inline-image-box`, see F10). Two entries — `horizontal-rule-tsdivider`
and `logo-latex2e` — no longer fire on this corpus, but they were already
dead before this round (checked by instrumenting `hunk_allowed` /
`apply_rewrites` on the base tree), so they belong to whoever owns the writer
change that stopped emitting them.

## 2. How the hunks were classified

**(a) Contract renames → `rewrite`.** The partial → contract macro renames of
`fragment-contracts.md` §1 and `decisions.md` X4 are folded onto one spelling
before diffing: `\marginnote`→`\tsaside`, `\keystroke`→`\tskeys`,
`\index`→`\tsindex`, `\texsmithHighlight`→`\tsmark`, `\acrshort`→`\tsacr`,
`\texsmithEmoji`→`\tsemoji`, `\texttt`→`\tscodeinline`, `\clearpage`→
`\tsdivider` (X2), `{todolist}`→`{tstasklist}`, `\item[\done]`→`\item[\tsdone]`,
`\text<slug>{`→`\tsscript{<slug>}{` (twenty scripts), and the whole `\tslogo`
family. These are one-sided spellings — the legacy text never contains the new
name — so the substitution is safe on both sides.

**(b) Intended semantic differences → `hunk`.** Where the change reshapes
arguments rather than renaming a macro, the hunk is matched by a pattern that
spells out the new argument grammar and cites the note that decided it:
`\begin{code}{lang}{title}{opts}` → `\begin{tscode}[lang=…, title=…, linenums,
hl_lines=…, engine=pygments]` (X3), `\begin{callout}[callout kind]{Title}` →
`\begin{tscallout}[kind=…, title=…]`, the progress bar, the autolink `\url`,
`\item{}`→`\item ` and the zero-width collapse around `\tsindex`
(`writers-and-passes.md` §2), the scripts pass re-grouping (§3 R4), the
snippet fallback and the dropped short caption. On the Typst side the same for
`#ts-callout`, `#ts-code`, `#raw(lang: …)`, `#ts-div("tab", …)` and the
unnumbered `#heading(…)` call.

**(c) Pure formatting → normalisation in `scripts/parity.py`.** Applied to
both sides, so it can never hide a one-sided difference:

- `tidy_tex_layout`: leading indentation; a blank line next to a block
  boundary (environment, sectioning, `\item`, table rule, float furniture —
  `\thispagestyle` was added, because the `pagestyle-dropped` rewrite used to
  orphan the blank line before it); `\vspace{…}\begin{…}` and
  `\end{…}\begin{…}` split onto two lines; a **sectioning** command's trailing
  `\label{…}` split onto its own line (a *caption's* label is deliberately
  left in place, so losing a float label still shows up); `\item[{ x }]`
  padding; `\PY{+w}{ }` → a plain space.
- `strip_typst_prelude` (new): the top-level `#let ts-…` bindings the tmark
  Typst writer inlines from `texsmith.typ` are dropped. This is the Typst twin
  of the `\providecommand{\tslead}` rule `writers-and-passes.md` §5 already
  lists, and it is what shrank the Typst diff from 15 465 to ~2 000 lines.
  It replaced the `typst-prelude` allow-list entry, which could not match once
  the prelude merged into a hunk with real content.
- `tidy_typ_layout`: a line opening with `]` joins the previous **non-blank**
  line and a blank line just after `[` is dropped (Typst trims a content
  block); a trailing comma before `)`; `#mi(```…```)` → `#mi(`…`)`; `--`/`---`
  → the dash they typeset as. One real harness bug was fixed here: a closing
  fence that carries the bracket of the call it sits in (```` ```] ````, which
  the `#ts-code` wrapper emits) was not recognised as closing, so the whole
  rest of the file stayed "inside a fence" on the tmark side and every
  subsequent line kept its indentation while the legacy side lost it.

**(d) Suspected bugs in the tmark path** — §3.
**(e) Bugs in the legacy path the new path fixes** — §4.

A note on the allow-list patterns: `parity.py` diffs with zero context, so two
adjacent but unrelated changes land in one hunk and a `\A…\Z` pattern then
fails. Splitting a heading's `\label` onto its own line removed the worst of
it (five combinatorial `heading-label-implicit-*` entries collapsed into one),
and the patterns that still suffer carry an explicit `(?:-\\label\{…\}\n)*`
prefix. Hunks that mix an intended change with a finding are left unlisted on
purpose — they are counted as findings.

## 3. Findings — suspected bugs in the tmark path

Ranked by severity. Every reproduction is a complete document; render it
twice with `--reader html` and `--reader tmark` and compare the body.

### F1 — the Typst template gets no document metadata (78 entries) — **fixed** (`1c8e1d6`)

`#set document(title: "")`, no rendered title block, and in the `letter`
template no `\opening` equivalent: `Dear Maestro Leonardo,` is simply absent
from `letter@typst/letter.typ`. The LaTeX path is unaffected (`\title{…}` and
`\maketitle` are correct), so the loss is between the tmark document model and
the Typst template context.

```markdown
---
press:
  subtitle: "A subtitle"
---
# My Title

Body text.
```

`--format typst`: legacy writes `title: "My Title"` plus
`#align(center)[#text(size: 1.8em, weight: "bold")[My Title]] #v(1.5em)`;
tmark writes `title: ""` and no title block at all.

Severity: **high** — every Typst document loses its title page. It is also
the single blocker keeping 84 Typst entries out of *allow-listed*.

**Fixed** in `1c8e1d6`. The legacy Typst path promotes the leading top-level
heading inside `_render_templated` (`_promote_title`) and the LaTeX path takes
the same decision in `prepare_for_conversion`, which `resolve_conversion_context`
calls; the Typst entry point gets the document straight from `prepare_documents`,
before either runs, so `extracted_title` was `None` while the `title` pass had
already dropped the heading from the body. Everything in the scaffolding hangs
off `{% if title %}`, hence the subtitle, the author block, the date and the
`letter` salutation going with it. `Document.promoted_title()` now states the
decision once — `PROMOTE_METADATA`, not suppressed by `--no-title`, heading
unique at its level, i.e. exactly when the `title` pass drops it — and the
templated IR branch asks for it; the context also carries the resolved
`language`. Standalone still keeps the heading in the body, as legacy does.

### F2 — front-matter `glossary.entries` are ignored (both backends) — **fixed** (`afeff69`)

Only acronyms declared with the inline `*[KEY]: …` syntax are recognised. An
acronym defined in the front matter is printed as plain text and never reaches
the glossary, in LaTeX and in Typst alike.

```markdown
---
glossary:
  entries:
    API: Application Programming Interface
---
# T

A REST API call.

*[NMR]: Nuclear Magnetic Resonance

NMR works.
```

legacy: `A REST \acrshort{API} call.` / `\acrshort{NMR} works.`
tmark: `A REST API call.` / `\tsacr{NMR} works.`

In `glossary@typst` six of the seven `/ term: definition` lines disappear from
the printed acronym list.

Severity: **high** — silent loss of markup and of glossary entries.

**Fixed** in `afeff69`, by a `glossary` pass — so **decision X5 is revised**:
it said "verify first, no pass by default" and named `examples/glossary` and
`examples/abbr` as the test, and they fail, which is X5's own condition for
adding one. The cause: the deprecated top-level `glossary:` key is hoisted
whole into `press.declare.glossary`, where tmark reads a *flat* `term →
definition` mapping (`tmark-registry`'s `collect::glossary`) — so `style`,
`groups` and `entries` became three glossary terms
(`\newacronym{style}{style}{long}`), the acronyms under `entries` became none,
and the writer's `abbr::keys`, which knows `Document.abbreviations` and
`declare.acronyms`, never saw them. The pass appends one `AbbrDef` per entry
(the IR twin of `append_synthetic_abbr_lines`) and leaves `declare.glossary`
holding only the flat terms it did not consume. `_declare_glossary` also
skips a term a cased variant already declares: tmark case-folds
`Resolved.glossary` while `\tsacr` keeps the acronym's spelling, so an acronym
both declared and written was printed twice.

The capstone on `tmark-migration` (`5dd9f8a`) meanwhile fixed the substitution
half differently, by appending the synthetic `*[KEY]: …` lines to the source
before `tmark.parse` (`documents._append_front_matter_abbreviations`). The two
compose — the pass adds nothing for a key already defined — and the pass is
still what keeps `style`/`groups`/`entries` out of the glossary.

### F3 — inline markup is flattened in a table **header** cell — tmark core

A header cell is rendered as plain text: inline code, strong, and — worst —
links lose their target. Body cells are correct.

```markdown
# T

| Key `tlmgr` name | **Bold head** | [Link](https://e.org) |
| ---------------- | ------------- | --------------------- |
| `body code`      | *em*          | plain                 |
```

legacy: `\textbf{Key \texttt{tlmgr} name} & \textbf{\textbf{Bold head}} & \textbf{\href{https://e.org}{Link}} \\`
tmark: `\textbf{Key tlmgr name} & \textbf{Bold head} & \textbf{Link} \\`

Severity: **high** — a hyperlink is destroyed with no diagnostic.
Seen in `docs/about/release-notes`, `docs/syntax/supported`, `fonts`.

### F4 — the lead-paragraph heuristic is inverted — tmark core

`writers-and-passes.md` §2 (Headings) defines `\tslead` as *a paragraph that
is a single `Strong` under 80 characters*. The tmark writer does the opposite:
it skips a paragraph that is only a `Strong` and fires on a `Strong` that
merely **starts** a paragraph or a list item.

```markdown
# T

**A whole paragraph in bold.**

> **A bold paragraph inside a quote.**

- **macOS:** install it

**Leading bold:** followed by text in a paragraph.
```

| source | legacy | tmark |
| ------ | ------ | ----- |
| whole-paragraph strong | `\tslead{…}` | `\textbf{…}` |
| whole-paragraph strong in a quote | `\tslead{…}` | `\textbf{…}` |
| list item starting with strong | `\item{} \textbf{…}` | `\item \tslead{…}` |
| paragraph starting with strong | `\textbf{…}` | `\tslead{…}` |

Severity: **medium-high** — `\tslead` adds `\par\noindent…\par\nobreak
\smallskip`, so firing it mid-sentence breaks the paragraph. 11+ entries,
both backends (`#ts-lead[…]` in Typst).

### F5 — an anchor-only link becomes literal text and the label is lost — tmark core

The `[](){ #id }` anchor idiom (used at the top of `docs/about/release-notes.md`)
produces an empty `\url{}` followed by the escaped attribute list, and the
`\label` is never emitted — so every `\hyperref[id]` to it dangles.

```markdown
[](){ #myanchor }
# T

See [here](#myanchor).
```

legacy: `\label{myanchor}` … `See \hyperref[myanchor]{here}.`
tmark: `\url{}\{\#myanchor\}` … `See \hyperref[myanchor]{here}.`

Typst is the same: `<releasenotes>` becomes `#link(""){\#releasenotes}`.

Severity: **high** — a broken cross-reference plus visible garbage.

### F6 — the SmartSymbols / smart-quote substitutions are not applied — tmark core

```markdown
# T

He said "straight quotes".

Copyright (c) 2025, tea (tm), reg (r).
```

legacy: `He said \enquote{straight quotes}.` and
`Copyright \texsmithEmoji{©} 2025, tea \texsmithEmoji{™}, reg \texsmithEmoji{®}.`
tmark: `He said "straight quotes".` and `Copyright (c) 2025, tea (tm), reg (r).`

Curly quotes typed directly are handled identically on both sides, so only the
ASCII shorthands are affected. 6+ entries (`letter-din`, `booby`,
`docs/about/license`, …).

Severity: **medium** — typography regression, no content loss.

**tmark core**: the tmark spec's gap table already lists `` `(c)`, `(tm)`,
`-->`, `1/2` `` as a `Str` the *parser* produces (class E, "smart symbols"),
so nothing on the TeXSmith side can supply them.

### F7 — the scripts pass misclassifies a Unicode superscript — **fixed** (`4540018`)

`docs/assets/examples/cheese`, `s⁻¹`:

legacy: `s\textsuperscript{-1}`
tmark: `s\tsscript{superscriptsandsubscripts}{\textsuperscript{-}}\textsuperscript{1}`

The classifier treats the `Superscripts and Subscripts` Unicode block as a
*script* (in the writing-system sense) and wraps it in `\tsscript`, and the
run is split between the sign and the digit.

Severity: **medium** — wrong macro, and the superscript is broken in two.

**Fixed** in `4540018`. `SuperscriptsAndSubscripts` is a ucharclasses *block*,
not a writing system, and its fallback entry names the document's own serif
face, so there is no font to switch to; it joins `latin`, `common`,
`punctuation` and `other` in `_SKIP_GROUPS`. `cheese` now writes
`s\textsuperscript{-1}`. Splitting the run between the sign and the digit is
the tmark writer's, and is what the legacy grouping did differently.

### F8 — `pymdownx.snippets` file includes are not expanded — tmark core

`--8<--- "examples/paper/code.py"` survives verbatim into the output (inside a
fence it is even syntax-highlighted as code); `docs/cli/index` keeps
`--8<-- "docs/assets/cli-help"`. `status.md` lists the snippet *preview* pass
as in progress, but this is the plain file-include form.

In `docs/syntax/supported` and `docs/assets/examples/cheese` the tmark line
additionally gains a stray leading `;` (`;--8<-- "…"`, `;[^1]: …`) that the
legacy output does not have — likely a definition-list marker leaking.

Severity: **medium** — the included file's content is missing.

**tmark core** (parser), verified: `tmark.parse` lowers `--8<-- "file"` to an
`Include` node and a fence's `--8<-- "file"` to the `include=` option, both of
which the `include` pass expands correctly. What it does not recognise is
`--8<--- "file"` — `pymdownx.snippets` accepts `-{2,}8<-{2,}`, and every
occurrence in the corpus (`docs/cli/index`, `docs/assets/examples/cheese`)
uses three dashes. The stray leading `;` is the same marker's *escape*
(`;--8<--` renders the marker literally), which the parser also does not
consume. The legacy path expands all of these.

### F9 — `[^1]` footnotes are not recognised in `docs/assets/examples/cheese` — tmark core

`Mozzarella [\^{}1]` and `;[\^{}1]: A high-moisture cheese…` reach the output
as literal text. A standalone footnote reproduction works on both readers, so
the trigger is context-specific (the surrounding definition list / the `;`
of F8) rather than footnotes as such.

Severity: **medium**, needs narrowing.

**tmark core**, and narrowed: the `;` of F8 is the trigger. Those lines are
`;[^1]: …` in the source — the snippet escape prefix again — so the footnote
definition is never recognised as one and the reference beside it stays
literal.

### F10 — a light/dark image pair is emitted twice (Typst) — **fixed** (`17852d1`), reclassified

`docs/index@typst` gains both `#box(image("ts-light.svg", …))` and
`#box(image("ts-dark.svg", …))`. `writers-and-passes.md` §2 (Media) says
`src#only-light|only-dark` is stripped, i.e. one variant is chosen.

Severity: **low-medium** — a duplicated logo.

**Reclassified and fixed** in `17852d1`: the pair is not duplicated, the
*legacy* Typst path lost both halves. `_build_image_map` resolved
`assets/ts-light.svg#only-light` as a file name, found nothing, and mapped it
to the empty string — which the writer reads as "drop this image". The LaTeX
writer strips the theme variant before resolving
(`_strip_mkdocs_theme_variant`) and emits both images, which is what tmark
does; `writers-and-passes.md` §2 says the fragment is *stripped*, not that a
variant is chosen. The Typst map now strips it too, keyed by the original
`src`. What is left on that page is the `#box(…)` the tmark writer puts around
an inline image so it cannot break — an intended difference, allow-listed as
`typst-inline-image-box`.

### F11 — smaller items

- `math@typst` loses `#set math.equation(numbering: "(1)")`, so display
  equations are unnumbered. **Fixed** in `7f6ade6`: the scaffolding gates that
  line on `uses_eqnref`, which the IR path set to a literal `False`. The Typst
  writer already says it — it names the `ts-equations` fragment when it emits
  an equation label or a reference to one — so the flag is that fragment being
  in the union of the bodies' `Requires`, which is what the legacy path read
  from `TypstWriterState.runtime["uses_eqnref"]`.
- Emphasis nesting order is inverted: `*_x_*` (legacy) vs `_*x*_` (tmark),
  `\textsc{\tscodeinline{…}}` vs `\textsc{\emph{\tscodeinline{…}}}` in `fonts`.
  Visually equivalent in Typst; the extra `\emph` in the LaTeX small-caps cell
  is a real difference. **tmark core** (writer).
- Inline code keeps the cell's trailing padding inside the span:
  `\tscodeinline{…</span>  }` in `docs/about/devel/index`. Not a bug: the
  source cell is `` `<span …></span>  ` `` and CommonMark strips a code span's
  padding only when there is one on *both* sides, so tmark is right and
  Python-Markdown was wrong — a §4 item rather than a finding.
- A code span whose text looks like a task item is parsed as one:
  `` `- [x] Done` `` renders as a task item, not as code
  (`docs/syntax/supported`). **tmark core** (parser).
- `\begin{enumerate}` / `\begin{description}` appear or disappear around
  nested lists in `docs/guide/features/headings` and
  `docs/guide/templates/fragments`. **tmark core** (writer).
- `#heading(level: 1, numbering: none, outlined: false)` — see open point O3.
  **tmark core** (writer).

## 4. Legacy bugs the tmark path fixes

- **L1 — the fence language was dropped.** `docs/about/devel/glossary.md`
  writes ` ```yml `; the legacy writer emitted `\begin{code}{text}{}{}`, so the
  block was never highlighted. tmark emits `lang=yml`. In Typst the legacy
  writer even rendered a whole code block as a *single-backtick* raw span
  (`docs/guide/fragments/index@typst`), losing the block layout; tmark emits a
  proper ```` ```python ```` fence.
- **L2 — `title:`, `linenums:` and `hl_lines:` were dropped in Typst.** The
  legacy Typst writer ignored those code-block attributes; tmark wraps the
  fence in `#ts-code(…)[…]`.
- **L3 — `::: module.path` was stripped inside a code span.**
  `docs/api/index` documents the mkdocstrings directive as `` `::: module.path` ``;
  legacy printed `module.path`, tmark keeps the text.
- **L4 — inline Pygments swallowed the whitespace tokens.** `code-inline`:
  legacy `\PY{p}{:}\PY{n+nb}{int}`, tmark `\PY{p}{:} \PY{n+nb}{int}` — the
  source is `haystack.find(sub: int) -> int`. Same in Typst.
- **L5 — nested task lists were flattened.** `docs/about/devel/index` has a
  three-level task list; legacy produced one flat `todolist`, tmark keeps the
  nesting. Legacy also omitted the unchecked box entirely (bare `\item`);
  tmark writes `\item[\tstodo]`.
- **L6 — critic markup was applied inside a code span.**
  `` `{++inserted text++}` `` became `\texttt{inserted text}`; tmark keeps the
  literal markers.
- **L7 — YAML table column widths and alignments were ignored in Typst.**
  `tables@typst`: legacy `columns: 3, align: (left, left, left)`, tmark
  `columns: (25%, auto, 15%), align: (left, left, center)`; likewise a
  spanning header cell now carries `align: center`.
- **L8 — the document subtitle was not rendered as Markdown.**
  `admonition-classic@typst` shows the legacy subtitle as literal
  `An Overview of **classic** framed elements`.

## 5. Decisions and open points

- **D1 — implicit heading labels.** The tmark LaTeX writer labels a heading
  only for an explicit `{#id}` or an implicit id that a reference targets;
  legacy labelled every heading with its slug
  (`writers-and-passes.md` §6, open question (b)). Allow-listed as
  `heading-label-implicit`. The residual risk is stated in §2(c): a
  *standalone* `\label` that tmark loses with nothing on the `+` side would be
  absorbed by that entry. Every such case seen so far (F5) has a `+` line and
  therefore stays visible.
- **O1 — should `parity.py` diff with one line of context?** Zero context is
  what makes the patterns combinatorial. One context line would split most
  merged hunks at the cost of a larger allow-list surface. Not changed here.
- **O2 — a link to a local `.md` file loses its target.** Documented as the
  links pass in `writers-and-passes.md` §3 and allow-listed
  (`snippet-link`, `typst-link-local-md`), but it is a silent loss of a
  hyperlink in every cross-page reference of the docs corpus. Worth a
  diagnostic rather than silence.
- **O3 — `outlined: false` on an unnumbered heading.** A document with
  `numbered: false` gets `#heading(level: N, numbering: none, outlined: false)`.
  `numbered: false` should not by itself remove the heading from the outline.
  Allow-listed as `typst-heading-unnumbered` pending a decision.
- **O5 — `\tsacr` first-use expansion. Decided (`4841f9d`): always the short
  form.** `ts-glossary` now defines `\tsacr` as `\acrshort`, not `\gls`. The
  author never writes the call — the writer substitutes every strict,
  case-sensitive match of a declared key, which `docs/syntax/abbr.md` states
  as "replaces … with `\acrshort{KEY}` … the substitution is the same
  regardless of where the acronym appears in the text" and the tmark spec
  (§Glossary and acronyms) as "maps to `glossaries`' `\acrshort`" — so a
  first-use expansion rewrites prose the author did not write and makes the
  print output say something different from the web profile, where the key
  stays inside `<abbr>`. The Typst contract already rendered the short form
  (`#ts-acr(key) = key`), so the two backends were inconsistent too. `\tsgls`
  keeps `\gls`: a glossary *term* reference (`@gls:term`) is written by the
  author, and there the `glossaries` convention applies. Recorded in
  `fragment-contracts.md` §1.
- **O4 — unresolved citations.** `docs/assets/examples/cheese` renders
  `[?Prentice1993]` under tmark where legacy printed the bare key. `[?key]` is
  the documented spelling for an unresolved reference, so the real question is
  why the key does not resolve in that entry.

## 6. PDF pixel diff

```
uv run python scripts/parity.py pdf --entries abbr counters index marginnote --reader-b tmark
```

Tectonic is provisioned by TeXSmith itself, so the command runs without any
extra setup; all eight builds succeeded. Overlays and `report.json` are under
`build/parity/pdf/`.

| entry | pages | worst page | text layer | verdict | after `4841f9d` |
| ----- | ----- | ---------- | ---------- | ------- | --------------- |
| `abbr` | 1 | **2.115 %** (page 1) | differs on 1 page | **differs** | **identical**, 0.000 % |
| `counters` | 3 | 0.000 % | identical | identical | identical |
| `index` | 4 | 0.000 % | identical | identical | identical |
| `marginnote` | 2 | 0.074 % (page 2) | identical | identical | identical |

`counters`, `index` and `marginnote` are pixel-identical or within the 0.1 %
threshold: `\tsindex`, `\tsaside` (including `side=left`) and the counter
contract typeset exactly as the legacy macros did. With O5 decided, the whole
PDF gate is clean.

### F12 — `\tsacr` expands the acronym on first use, `\acrshort` never did — **decided and fixed** (`4841f9d`)

This is what `abbr` differs on, and the text parity cannot see it: the
`acronym` allow-list entry folds `\acrshort{key}` onto `\tsacr{key}`, but the
two macros do not typeset the same thing. Page 1 of `abbr`:

```
legacy: … techniques like NMR, FTIR, and GC-MS are essential …
tmark:  … techniques like Nuclear Magnetic Resonance (NMR), Fourier
        Transform Infrared Spectroscopy (FTIR), and Gas Chromatography–Mass
        Spectrometry (GC-MS) are essential …
```

So `\tsacr` in `ts-glossary` behaves like `\gls`/`\acrfull` rather than
`\acrshort`. Either is defensible — first-use expansion is the usual
`glossaries` convention — but it is a change of rendered output that no text
allow-list entry records, and it must be an explicit decision (**O5**) rather
than a side effect of the rename. It was taken: **always the short form**
(O5), so `\tsacr` is `\acrshort` and the `abbr` PDF entry is identical again.

Severity: **medium** — visible in every document that uses acronyms.
**Decided and fixed**: see O5 above; `abbr` is now pixel-identical.

## 7. Closing note — the cross-reader comparison is retired, and deleted

This document records a measurement that can no longer be repeated as it was
taken. `scripts/parity.py diff` rendered the *same* source with both readers,
and since the flip every source in `examples/**` and `docs/**` is canonical
TMark, which the legacy `html` reader cannot parse — it rendered `{.thin}`,
`{raw latex}(…)` and `::: tabs` as literal text. A whole-corpus run therefore
reported noise, not findings, and the numbers in §1 and §1.1 are a snapshot of
the sources as they stood on 2026-09-12, before the rewrite.

Phase 5 then deleted the legacy pipeline outright — the Python-Markdown
extensions, the Python writers, the hand-written IR, the `html` reader and the
CLI's `--reader` option. With one reader left there is nothing for a
cross-reader comparison to compare, so `diff` and `tests/parity/allow.yml` (86
entries: 59 `rewrite`, 27 `hunk`) were deleted too. This file is what survives
of them: the record of what the migration changed and why each difference was
accepted. Do not expect to re-run the commands quoted above; read them as the
minutes of a measurement.

What replaces it as a gate is `parity.py baseline --check`, which re-renders the
corpus and compares it to a committed record (`writers-and-passes.md` §5,
`status.md`, "What the harness measures now"). The baseline was re-recorded on
2026-09-12; the legacy renders this file's tables were computed against are gone
from the tree.

**Findings closed.** F1, F2, F7, F10, F11's `uses_eqnref` item and F12/O5 on the
TeXSmith side, each with its commit in §3; F3, F4, F5 and F6 on the tmark side.
§4's L1–L8 are improvements the new path brought and need no follow-up.

**Findings still open**, none of them measurable by the harness any more — each
now needs its own reproduction, and the ones in the writer or the parser belong
to tmark:

- **F8** — `--8<--- "file"` (three or more dashes, which `pymdownx.snippets`
  accepts and every occurrence in the corpus uses) is not lowered to an
  `Include`, and the `;--8<--` escape is not consumed. tmark parser; being
  fixed at the time of writing.
- **F9** — the `[^1]` footnotes of `docs/assets/examples/cheese`. Narrowed to
  F8's stray `;`: closes with it, worth re-checking after.
- **F11**, the tmark-core items: emphasis nesting order (`*_x_*` vs `_*x*_`, and
  the extra `\emph` in a small-caps cell); a code span whose text reads as a
  task item being parsed as one; `\begin{enumerate}` / `\begin{description}`
  appearing or disappearing around nested lists.
- **O2** — a link to a local `.md` file loses its target silently. Documented
  and allow-listed, but it deserves a diagnostic.
- **O3** — `numbered: false` also sets `outlined: false` on a Typst heading.
  Still undecided.
- **O4** — the unresolved citation in `docs/assets/examples/cheese`: `[?key]`
  is the documented spelling, so the question is why the key does not resolve.
- **O1** — whether the harness should diff with one line of context. Moot for
  the baseline gate, which prints whole hunks for review; it only ever mattered
  for the allow-list patterns.

§6's PDF pixel diff is likewise a two-reader measurement. What guards the
rendering now is `parity.py pdf --baseline --check` over the same four entries
(`abbr counters index marginnote`), against `tests/parity/pdf-baseline.json`.
