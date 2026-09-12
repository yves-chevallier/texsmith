# Examples migration inventory

Status: measured 2026-09-11 against `~/tmark/target/release/tmark` (M1–M3) and
TeXSmith `tmark-migration`. Companion of `specs/tmark-migration.md` (§1 table,
§5 gap audit, D0, R10). Goal it measures: every directory under `examples/`
builds to PDF once its Markdown is in canonical TMark. Method: for each `.md`
(`build/`, `site/` and `README.md` excluded) run `tmark check`, `tmark parse`
(IR walked for legacy text left in `Str`), `tmark fmt` (diffed, spot-checked)
and `tmark lint --fix` on a scratchpad copy; grep the sources with the pattern
list of `specs/migration/` (script kept in the session scratchpad, not
committed). Nothing under `examples/` was changed.

Two facts shape everything below. `tmark lint --fix` rewrites the file **in
place** and prints only "N fix(es) applied" (the plan says it prints the text:
run it on copies). And the `///` fix is wrong for every use the examples make
of it: `/// latex` → `::: latex` and `/// caption` → `::: caption` both land on
`container-unknown`, so the one fix that fires most often makes things worse.

## 1. Per-example table

Difficulty: S = parses clean today or after `lint --fix`; M = one tmark fix or
one TeXSmith pass away; L = a spec decision or several gaps. Counts are
occurrences in the sources (code fences excluded unless the row is a fence).
Diagnostics are from `tmark check` on the untouched source.

| Example (in `examples/Makefile`?) | Sources | Legacy spellings used | `check` diagnostics | fmt changes meaning? | Diff. | Blockers |
| --- | --- | --- | --- | --- | --- | --- |
| abbr (yes) | abbreviations.md (10) | `*[abbr]:` ×6 | none | no | S | — |
| admonition (yes) | admonition.md (68) | `!!!` ×17 incl. Material types `caution summary success failure bug quote` and custom `unicorn`; `{{callouts.style}}` inside front matter | none | no (`!!!` → `:::`) | S | custom type declared as `press.callouts.custom.unicorn` (spec: `press.callouts.unicorn`) |
| booby (yes) | booby.md (23) | — | none | no | S | — |
| book (yes) | book.md (468) + book.bib | `^[key]` ×83, `{index}[…]` ×123, `*[abbr]:` ×10, `/// caption` ×6, `/// latex` ×2, `$…$` ×2 | deprecated 8, container-unknown 8 | **yes**: 39 `^[` stay literal and 22 `^[a] … ^[b]` pairs become `Superscript` swallowing the prose between | L | citations; `///` fix; `press.fonts`, `admonition_style`, `slots`, `imprint` in `extra` |
| code (yes) | code-block.md (34), code-inline.md (8) | `` `#!c …` `` ×2, `title=`/`linenums=`/`hl_lines=` | none | no (`{code lang=c}[…]`) | S | — |
| colorful (yes) | colorful.md (34) + manifest/template | — | position-word 1 | no | S | template `.`; four heading slots |
| counters (no) | counters.md (117) | `#{prefix:key}` ×10 (8 declared, 2 prose), `@ref` ×14, `@[ref]` ×1, top-level `counters:` | deprecated 8, deprecated-frontmatter-key 1, position-word 3 | no (`{counter}(…)`, prose `#{` escaped) | S | front-matter key moves by hand (no fix) |
| custom-render (no) | none (counter.py, API on `<span class="data-counter">`) | raw HTML hook | n/a | n/a | M | rewrite as an IR pass or a `::: ` container (R2) |
| diagrams (yes) | diagrams.md (32) + pgcd.drawio | `/// caption` ×1, `.drawio` image, ```` ```mermaid {width=80%} ```` | deprecated 1, container-unknown 1 | **yes**: `{width=80%}` on the mermaid fence dropped | M | `///` fix; fence attribute list |
| dialects (yes) | dialects.md (231) | — | position-word 1 | no | S | script-detection pass (TeXSmith) |
| emoji (yes) | emoji.md (70) | `/// latex` ×1, literal emoji, def list | deprecated 1, container-unknown 1 | no | S | `///` fix; emoji font pass (TeXSmith) |
| fonts (yes) | fonts.md (36) | `__smallcaps__` ×16 | none | no (`{sc}[…]`) | S | `press.fonts` |
| glossary (yes) | glossary.md (59) | top-level `glossary:` (style/groups/entries), `*[abbr]:` ×1; acronyms detected from prose, no markup | deprecated-frontmatter-key 1 | no | S | glossary pass keyed on `declare.glossary` (TeXSmith) |
| index (yes) | index.md (27) | `#[…]` ×7, `{latex}[…]` ×2 | deprecated 2 | no | S | — |
| letter (yes) | letter.md (48) + svg | — (all in `press.from/to/signature/ps/back-address`) | none | no | S | letter keys in `extra` |
| marginnote (yes) | marginnote.md (76) | `{margin}[…]{l\|r}` ×8, `{latex}[…]` ×1, `{index}[…]` ×1 | **error** frontmatter-yaml 1 (`press.authors: [TeXSmith]`), deprecated 8, position-word 2 | no (`{aside side=left}[…]`) | M | tmark rejects a string author |
| markdown (yes) | features.md (627) + hanoi.py | `=== "Tab"` ×2, `[=n% "…"]{: .thin}` ×4, `:smile:` ×2, `^^ins^^` ×1, `--8<-- "hanoi.py"` inside a `python` fence ×1, `/// latex` ×1, `{latex}[…]` ×1, `!!!` `???`, `$$` ×4, `---` ×2, `[^1]`, `==` `~~` `^` `~` `__`, `_em_`, 41 `md` doc fences | deprecated 2, container-unknown 1, lead-promotion 1 | **yes**: tab titles escaped and tab bodies become code blocks; `^^ins^^` escaped; the rest is literal text | L | tabs (decision), ProgressBar (M5), emoji shortcodes, `^^…^^`, fence `include=`, `{: .x}` attr spelling |
| math (yes) | math.md (35) | `\(…\)` ×3, `$$` with `\begin{align}`+`\label`, `$\eqref{}$` | none | no (`\(…\)` → `$…$`) | S | — |
| mermaid (yes) | mermaid.md (17) | bare ```` ```mermaid ````, `.mmd` image, `pako:` URL image | none | no (`mermaid image`) | S | assets pass (TeXSmith) |
| mkdocs (yes) | docs/{index,foo,bar,baz,qux}.md (5×≤21) + mkdocs.yml | `!!!` ×1, ```` ```md {.snippet caption="…" width="60%"} ```` ×1 | none | **yes**: info-string attrs mangled to `width="\"60%\"}"`, `.snippet` lost | M | info-string attribute list; site side is R8 |
| multi-document (yes) | a.md b.md c.md (3 each) + config.yml | — | none | no | S | `ResolveOptions.start` chaining (3.4) |
| paper (yes) | cheese.md (240) + cheese.bib, docs/cheese.md (138) + mkdocs.yml | `[^key]` ×3 (keys in `.bib` and in front-matter `bibliography`), `[^1]` ×1, `/// figure-caption` `/// table-caption` ×3–4 with an indented `attrs: {id: …}` line, `[](#id)` ×3, `$…$` ×9, `$$` ×4, `.svg` image, `python` fence | deprecated-frontmatter-key 1, deprecated 3–4, container-unknown 3–4, ref-unresolved 3 | **yes**: `[^key]` escaped to `\[\^key]`; `attrs:` line turned into a code fence inside `::: table-caption` | L | citations; caption-block fix (ids live on the `attrs:` line, refs unresolved until then); `.bib` on the CLI |
| progressbar (yes) | progressbar.md (15) | `[=n% "…"]{: .candystripe\|.thin}` ×4 | none | no (literal) | L | ProgressBar node (M5), `{: .x}` spelling, `ts-extra` macro |
| recipe (yes) | none (cake.yml → API `ConversionService` + template) | — | n/a | n/a | S | audit the YAML text fields when the API switches reader |
| snippet (yes) | docs/index.md (15) | ```` ```markdown {.snippet caption= width=} ```` ×2 (one nested ```` ```` ````) | none | **yes**: same info-string mangling | M | info-string attribute list; snippet pass (TeXSmith) |
| tables (no) | tables.md (655) | `yaml table` ×15 (5 rejected), `Table:` before ×9, `<br>` ×2, `[…]{label=…}` ×1, `@ref` ×1 | fence-unknown-node-word 5, position-word 6 | **yes**: grouped-header cells `[Apples, [120,…], [130,…]]` printed as `[Apples, "", ""]`; `table:` settings and `width-group` dropped; a rejected fence is printed as plain ```` ```yaml ```` | L | table model (R6) + printer data loss |
| typst-article (yes) | article.md (65) | `~~del~~`, `\(…\)`, `---`, python fence | none | no | S | — |
| typst-hello (yes) | hello.md (13) | `---` | none | no | S | — |

Totals: 34 source files, 3 232 lines. `lint --fix` applies 37 fixes across 9
files (book 8, counters 8, marginnote 8, paper 3 + 4, index 2, features 2,
diagrams 1, emoji 1); 18 of those are the wrong `///` rewrite. Residual after
fix: 18 `container-unknown`, 5 `fence-unknown-node-word`, 6 `ref-unresolved`,
3 `deprecated-frontmatter-key`, 1 `frontmatter-yaml` error, 17 hints/infos.

## 2. Legacy spellings, aggregate

"Today" = what the release binary does with the spelling: **fix** (rewritten
by `lint --fix`), **fmt** (parsed, printer normalises, no fix attached),
**sugar** (parsed, indefinite horizon), **diag** (parsed with a diagnostic, no
fix), **literal** (plain `Str`, no diagnostic), **broken** (parsed into
something else).

| Legacy spelling (count) | Canonical | Today | tmark must add | TeXSmith must add |
| --- | --- | --- | --- | --- |
| `#{prefix:key}` (10) | `{counter}(prefix:key)`, sugar `#(…)` | fix (declared prefixes only, C16) | — | — |
| `[^key]` citation (6) | `@key` | literal | tokenizer rule: `[^k]` with no `[^k]:` definition is a `Cite`, plus a fix (`.bib` on the CLI is invisible to `check`, so key the rule on the missing definition, not on the registry) | pass `.bib` paths to `resolve` |
| `^[k1,k2]` (83) | `@[k1; k2]` | literal; two in one paragraph → **broken** (`Superscript`) | same rule; `^[` must never open a caret superscript | — |
| `{latex}[…]`, `{typst}[…]` (4) | `{raw latex}(…)` | fix | — | — |
| `/// latex … ///` (4) | ```` ```latex raw ```` fence | **broken fix** (`::: latex`) | route backend names (`latex typst html`) to a raw fence in the `///` fix | — |
| `/// caption`, `/// figure-caption`, `/// table-caption` (+ indented `attrs: {id: …}`) (14) | `Figure:`/`Table:` line after the float with `{#id}` | **broken fix** (`::: caption`, `attrs:` line → code fence, `{#id}` escaped) | dedicated lowering + fix: kind from the block name or the neighbouring float, id from the `attrs:` line | 0.1 (caption after the float) already planned |
| `{margin}[…]{l\|r\|o\|i}` (8) | `{aside side=…}[…]` | fix | — | rename `MarginNote` → `Aside` |
| `--8<-- "file"` at block level (0 in examples) | `{include}(file)` | fix | — | include pass |
| `--8<-- "file"` inside a code fence (1) | ```` ```python include="hanoi.py" ```` | invisible (fence text) | fix: a fence whose body is one snippet line → `include=` option | the `include` pass reads the file |
| `Table:` before the table (9) | `Table:` after | sugar (fmt moves it) | — | — |
| `[](gls:term)` (0 here; skill and docs teach it) | `@gls:term` | **broken**: `Link` to URL `gls:API`, silent (C20) | deprecation + fix | — |
| `{index:r}[…]` (0 here) | `{index registry=r}[…]` | diag + fmt, no fix | attach the fix | — |
| `{index}[…]{b}` / `{i}` (0 here) | `{index main=true}[…]` | literal `{b}` (C20) | deprecation + fix | — |
| `#[term]` (7) | `{index}[term]` | sugar (fmt prints the role) | — | — |
| top-level `counters:` `bibliography:` `glossary:` (3) | `press.declare.*`, `press.sources.*` | typed + `deprecated-frontmatter-key`, no fix | a YAML-rewriting fix, or leave it to a script | migration script if tmark declines |
| `press.admonition_style` (1) | `press.callouts.style` | in `extra`, silent (spec names `callout_style`) | — | accept both, deprecate the old |
| `press.authors: [string]` (1) | `authors: [{name: …}]` | **error** `frontmatter-yaml` | accept the string form (C9 says tolerate) | — |
| `=== "Tab"` (2) | none | **broken**: title literal, body becomes a `CodeBlock` | spec decision (drop for print / `::: tabs`); until then a `strict-x-construct`-style diagnostic instead of silence | render as titled sections if "drop" |
| critic `{--…--}` etc. (0 here) | M5 nodes | literal | M5 | — |
| `[=45% "label"]{: .thin}` (8) | `ProgressBar` | literal | M5 node; note the Python-Markdown `{: .x}` attr spelling | `ts-extra` bar macro |
| `[[wiki]]` (0 here) | `Link` (class D) | literal | M5 | — |
| `:material-…:` (0 here) | none | literal | spec decision or drop | — |
| `:smile:` (2) | `Str` with the code point (class E) | literal shortcode | expand shortcodes in the tokenizer (E class says `Str`) | emoji font pass over `Str` |
| `^^ins^^` (1) | `{underline}[…]` (needs `inline.insert`) | literal, fmt escapes it | implement or declare unsupported | — |
| `LaTeX`, `XeLaTeX` words (26) | none (`TexLogo` today) | `Str` | spec decision: `{tex}` role or nothing | `Str` pass keyed on a feature |
| `---` page break (6) | `HorizontalRule` | parsed | — | writer option / `\tsdivider` (partial triage) |
| ```` ```md {.snippet caption="…" width="80%"} ```` (3) | to decide (`md snippet` data directive?) | **broken**: `.snippet` dropped, `width="\"80%\"}"` | attribute list on info strings (C1 value grammar) | snippet pass (`CodeBlock` → nested build → `Image`) |
| ```` ```mermaid {width=80%} ```` (1) | `mermaid image {width=80%}`? | **broken**: attrs dropped by fmt | keep fence attributes | — |
| `yaml table` (15) | same | 10 parse, 5 rejected; fmt loses grouped cells and prints rejected fences as ```` ```yaml ```` | model: named-row mode, `separator: {label}`, `label`/`cells` rows, integer `name`, `table:` settings, `width-group`, nested per-group cell arrays; printer must round-trip or refuse (R6) | validation pass until then |
| bare ```` ```mermaid ```` (3) | `mermaid image` | sugar | — | assets pass |
| `!!!` / `???` (20) | `::: type {…}` | sugar (fmt rewrites) | — | validate custom types |
| `<!-- -->`, raw HTML (2) | `Comment`, `RawBlock/RawInline html` | parsed; `<div markdown>` content swallowed | decision C19 | `<br>` in cells kept (fixture exists) |
| `{{ key }}` (1) | `Var` | parsed | — | `var` pass |
| `$$`, `\begin{align}`, `\label`, `$\eqref{}$` (25) | same | parsed (class D) | — | — |
| `\(…\)`, `\[…\]` (6) | `$…$`, `$$…$$` | fmt | — | — |
| `` `#!py …` ``, `++k++`, `==`, `~~`, `^`, `~`, `__sc__` (25) | roles | fmt | — | — |
| `_emph_` (many) | `*emph*` | fmt | — | — |
| `[TOC]` (0 here) | ignored | literal `[TOC]` | drop it as the appendix says | — |
| fancy lists `a.` `i.` (0 here; features.md nests `a.` under `1.`) | `OrderedList{style}` | **broken**: paragraphs | M5 | — |
| `[…]{label=x}`, `{regex=…}`, `{lang=en}` (1) | `Span{attrs}` | parsed | — | passes for `label`/`regex` roles |
| heading slug refs `[](#my-heading)` (0 here; docs likely) | explicit `{#id}` | ref-unresolved | decide: auto-ids for headings or lint | — |

R10 behaviour changes seen in the examples: lazy continuation after a list
(`emoji.md` line 37 joins the last item), nested-list re-indentation, `_x_` →
`*x*`, footnote and `*[abbr]:` definitions hoisted to the end of the file,
`:   ` definition-list spacing, a blank line after the front matter. All
meaning-preserving; none needs a fix.

## 3. Front-matter keys

| Key | Used by | tmark | Note |
| --- | --- | --- | --- |
| `title`, `subtitle`, `date` (root or `press`) | book, counters, glossary, booby, colorful, marginnote, paper, typst-* | typed | `press` wins; a free-text date (`October 20, 2025`) is accepted as a string |
| `authors` | marginnote, paper | typed (`[{name, affiliation, email}]`) | a bare string item is a hard error; TeXSmith accepts it |
| `author` (singular), `publisher`, `edition`, `imprint.*` | book, counters, booby, features | `extra` | book template metadata |
| `language`, `toc` | counters, glossary, features | `extra` | spec key is `lang`; `toc` is `press.toc` in the spec |
| `id`, `lang`, `epigraph` | none | typed | — |
| `press.template` | booby, book, colorful (`.`), letter | `extra` | TeXSmith |
| `press.base_level` | book (`part`) | typed | — |
| `press.paper` (+ `.margin`), root `paper` | book, admonition, diagrams, index | `extra` | — |
| `press.columns`, `press.numbered`, `press.paragraph.*`, `press.colors.*`, `press.override.preamble`, `press.keywords`, `press.description` | admonition, dialects, emoji, colorful, features | `extra` | — |
| `press.slots.*` | book, colorful, dialects, features, paper, mkdocs.yml | `extra` | heading-text selectors only (R5) |
| `press.fonts`, `press.admonition_style` | book | `extra` | `admonition_style` is TeXSmith's real key; the spec deprecates `callout_style` → `callouts.style`; align the two |
| `press.callouts.custom.<type>.{background_color, border_color, icon}` | admonition | `extra` | spec shape is `press.callouts.<type>.{icon, color}` and `declare.admonitions.<type>` |
| `press.from/to/signature/ps/back-address/date` | letter | `extra` | letter template |
| `counters:` (top) → `press.declare.counters` | counters | typed + diag | `name`, `format`, `start` all typed |
| `bibliography:` (top) → `press.sources.bibliography` | paper | typed + diag | DOI string form accepted |
| `glossary:` (top) → `press.declare.glossary` | glossary | typed + diag | `style`, `groups`, `entries` pass through untyped (`any`) |
| `crossrefs:`, `admonitions:`, `acronyms:` (top) | none in examples | typed + diag | — |
| MkDocs `plugins.texsmith` (`books`, `root`, `base_level: -1`, `paper`, `slots`) | mkdocs, paper/docs | not seen by tmark | companion config (3.9) |
| `config.yml` `press.title/subtitle` | multi-document | not seen | TeXSmith merges it |

## 4. Work items, in order

Completion criterion: `for f in examples/**/*.md: tmark lint --fix; tmark
check --strict` reports nothing, `tmark fmt --check` passes, and every
`make -C examples` target builds. Item numbers refer to the plan where one
exists.

tmark

1. `lint --fix`: add `--stdout`/`--diff`; document that the default writes in place.
2. Citations: `[^key]` without a definition and `^[k1,k2]` lower to `Cite`
   with a `deprecated` fix (`@key`, `@[k1; k2]`); `^[` never starts a caret
   superscript (plan §5 "footnote-versus-citation shadowing"). Unblocks book, paper.
3. `///` fix: backend names → raw fence; `caption`/`figure-caption`/
   `table-caption` → caption line after the float, id read from the indented
   `attrs:` line. Unblocks book, paper, diagrams, emoji, features.
4. Info-string attribute lists (`{.snippet caption="…" width="60%"}`,
   `mermaid {width=80%}`): parse with the C1 value grammar, keep classes,
   print them back. Unblocks snippet, mkdocs, diagrams.
5. Front matter: accept a string author; attach a fix to
   `deprecated-frontmatter-key` (YAML rewrite of the five top-level groups);
   recognise `admonition_style` alongside `callout_style`. Unblocks marginnote.
6. C20 rows: `[](gls:term)`, `{index}[…]{b}`, `{index:r}` get a diagnostic and a fix.
7. Table model (R6): the five rejected shapes of `tables.md`, `table:`
   settings, `width-group`, nested per-group cell arrays; the printer must
   never flatten cells or drop the `table` word of a rejected fence.
8. Fence snippet: a code fence whose body is a single `--8<-- "file"` line →
   `include="file"` fix.
9. Silence is the enemy: tabs, critic, progress bars, wiki links, fancy
   lists, `^^…^^`, `:material-…:`, `[TOC]` currently parse as plain text
   with no diagnostic. Until M5 lands, emit `strict-x-construct` (or a new
   `compat-unsupported`) so `check --strict` fails on them.
10. Spec decisions (0.4, one challenge each): tabs; TeX logos; icon
    shortcodes; emoji shortcodes expanded by the tokenizer (class E says
    `Str`); `---` rendering; `<div markdown>` (C19); heading auto-ids.
11. M5 nodes the examples need: `ProgressBar` (progressbar, features),
    fancy lists (features). Critic and wiki links are not used by any example.

TeXSmith

1. Phase 0.3: `tmark check` + `fmt --check` over `examples/` in CI, with the
   counts of §1 as the baseline so regressions are visible.
2. Front matter (`core/metadata.py`): accept `authors` as tmark types it,
   `lang` as an alias of `language`, `press.callouts.style` as the canonical
   spelling of `admonition_style`, and `press.callouts.<type>` beside
   `press.callouts.custom.<type>`. Validate `extra`.
3. Passes (3.3) the examples exercise: `var` (admonition), `assets` (mermaid,
   diagrams, paper svg, letter svg, emoji fonts), `snippet` (snippet, mkdocs),
   `scripts` (dialects), `glossary` (glossary: acronyms detected from prose,
   `*[abbr]:`), `include` (features `hanoi.py`), `slots` (book, colorful,
   dialects, features, paper), TeX-logo `Str` pass if item 10 decides so.
4. Resolution (3.4): `.bib` files from the CLI into the `Loader` (book, paper);
   `ResolveOptions.start` chaining (multi-document); `refs.json` untouched.
5. Fragments (3.6): `ts-extra` progress bar macro, `\tsdivider` for `---`,
   custom callout colours from `press.callouts.*`, `Aside` sides.
6. Non-mechanical example edits, after the tmark items: features.md tabs
   (per decision 10), `^^ins^^`, `:smile:`; progressbar `{: .x}` → `{.x}`;
   custom-render rewritten as an IR pass; recipe's YAML text fields audited.
7. Docs and skill (4.3): `writing-texsmith` still teaches `/// caption` with
   `attrs:`, `[^key]` citations, `[](gls:)`, `{latex}[…]`, `--- ` page
   breaks; rewrite once items 2–6 exist so new documents start canonical.

## 5. After wave 1 (tmark `fixes` and `tables` merged, 2026-09-11)

Measured by the `fixes` agent on copies of the examples: `tmark lint --fix
--stdout`, then `tmark check` with the sibling `.bib` files, then `--strict`
on the fixed copy.

| File | Before (§1) | After `--fix` | `--strict` |
| --- | --- | --- | --- |
| book/book.md | 8 container-unknown, 8 deprecated, 83 `^[` silent or broken | none (83 citations rewritten, all resolve against `book.bib`) | ok |
| paper/cheese.md | 3 container-unknown, 3 deprecated, 1 frontmatter-key, 3 ref-unresolved | 3 caption-id-off-convention hints, 1 position-word | ok |
| paper/docs/cheese.md | 4 container-unknown, 4 deprecated, 3 ref-unresolved | 4 hints, 3 ref-unresolved (`.bib` named by `mkdocs.yml`, one directory up) | fail |
| diagrams, emoji, glossary, index | 1–2 each | none | ok |
| counters/counters.md | 8 deprecated, 1 frontmatter-key | 3 position-word | ok |
| marginnote/marginnote.md | frontmatter-yaml **error**, 8 deprecated | 2 position-word | ok |
| markdown/features.md | 1 container-unknown, 2 deprecated | 9 compat-unsupported (tabs, progress bars, emoji, `^^…^^`, fancy lists: milestone 5) | fail, intended |
| progressbar/progressbar.md | silent | 4 compat-unsupported | fail, intended |
| tables/tables.md | 5 fence-unknown-node-word | 13/13 fences lowered; 3 deliberate error cases carry 5 `table-*` errors; `fmt` is a fixed point | fail, intended |
| the 21 others | none / hints | unchanged | ok |

Residual across the corpus: 0 `container-unknown`, 0 `frontmatter-yaml`, 0
`deprecated`, 0 `deprecated-frontmatter-key` after `--fix`. What remains is
the milestone-5 constructs (`compat-unsupported`), which the spec wave is
deciding, and `.bib` discovery for the MkDocs-hosted paper.

## 6. Closing section — the flip (plan 4.3, 2026-09-12)

Every `.md` under `examples/` is now written in canonical TMark, in place, and
`--reader` defaults to `tmark`. The per-example record of what changed, the
build table, the diagnostics deliberately kept and the findings are in
`examples-flip.md`; this section closes the work items of §4.

**tmark items.** 1 (`--stdout`/`--diff`), 2 (citations), 3 (the `///` fix), 4
(info-string attribute lists), 5 (front matter: string author, the
`deprecated-frontmatter-key` YAML fix, `admonition_style`), 6 (the C20 rows), 8
(a fence whose body is one snippet line) and 9 (silence → diagnostics) all
landed and were exercised across the corpus: `tmark lint --fix` alone brought
the 130 `deprecated`, 4 `deprecated-frontmatter-key` and 1 `frontmatter-yaml`
records of §1 to zero. Item 7 (the table model) landed; `tables.md` keeps five
`table-*` errors, which are the deliberate mistakes of its "Error cases"
section. Item 11's `ProgressBar` and fancy lists parse; item 10's decisions are
in the spec — tabs are `:::: tabs` / `::: tab {title=…}`, emoji shortcodes
expand to the character, icon shortcodes are web-only, `^^x^^` needs the
`inline.insert` feature. Nothing in the examples reports `compat-unsupported`
any more.

**TeXSmith items.** Item 2 (front matter) is done as far as the examples
exercise it, plus two cases this task found: `press.declare.glossary` is read
where `glossary:` was, and its entries reach the body again as synthesised
abbreviation definitions (finding F1 of `examples-flip.md`, decision X5 —
`examples/glossary` was precisely the trigger it named). Item 3's passes all
run on the default path. Item 6 (non-mechanical edits) is done except
`custom-render`, which still drives the API through a raw-HTML hook and wants
an IR pass — since closed by deletion: phase 5 removed the example with the
`@reads` / `@writes` decorators it existed to demonstrate. Item 7 (docs and the `writing-texsmith` skill) is **not** part of
this task: `docs/cli/index.md` and the changelog were updated for the new
default, the syntax pages and the skill are plan task 5.3.

**What the fixer did not cover**, and had to be written by hand against the
spec: content tabs, `^^x^^`, `???+ note "Title"`, `!!!` → `:::` (sugar the
fixer leaves alone by design), a `:::` callout of a type nobody declared,
`[](#id)` → `@id`, `#[term]` → `{index}[term]`, `` `#!c …` `` →
`{code lang=c}[…]`, a bare ```` ```mermaid ```` fence → ```` ```mermaid image ````,
`\(…\)` → `$…$`, and the list-item continuations `lint --fix` flattens
(finding F3).

**What was deliberately left in a sugar spelling**, because the document
exists to demonstrate it or because MkDocs Material renders it natively:
`~~del~~`, `==mark==`, `^sup^`/`~sub~`, `++Ctrl+C++`, `__smallcaps__`,
`:smile:`, `\(…\)` in `math.md`, and the `!!!` callout of `examples/mkdocs`.
Those files are accepted by `tmark check --strict` but are not fixed points of
`tmark fmt`; the gate this task drove to zero is `check --strict`, not
`fmt --check`.
