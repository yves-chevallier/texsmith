# Web profile — TMark constructs on a MkDocs site (R8, D5/R9)

Status: design note, 2026-09-11. Owner of migration plan items 1.7, 3.8, 3.9
and difficulties R8, R9. Companion of `~/tmark/design/04-printer.md`
§Profiles and `07-writers.md`.

## Problem

MkDocs renders pages with Python-Markdown; the TMark constructs a TeXSmith
author writes (`@fig:x`, `#(fw:x)`, `::: figure`, `Figure:` lines,
`{index}`, `{aside}`, `yaml table` fences, `::: warning`) are invisible to
it. Today TeXSmith's Markdown extensions and two MkDocs plugins
(`texsmith.counters`, `texsmith.index`) render them, with site-wide
numbering from a regex pre-pass over the nav. Phase 5 deletes every
extension. The site must still show numbered items, cross-page references,
captions and callouts, and the PDF export of the same site must carry the
same numbers. `Profile::Mkdocs` is a stub that prints like `Canonical`.

## Constraints

- The site pipeline stays Material's: `toc` ids, search, annotations, tabs,
  icons, `mkdocstrings`, `macros`, custom fences and the `snippets` URL
  rewriting all run on Python-Markdown output. Replacing Python-Markdown
  for the page body is a Material fork.
- The parser is CommonMark, Material is not (R10), and the parser closes an
  unclosed `:::` at end of document. `::: pkg.mod` (mkdocstrings, 8 pages
  of `docs/`) has no closing fence: a whole-document re-print would swallow
  the rest of the page into a `Div`.
- MkDocs renders page by page; forward references across pages need the
  numbers before the first page renders (a pre-pass stays).
- One registry for web and PDF (D4). `Resolved` numbers TeXSmith-numbered
  series only; the web has no backend to number `fig`/`tbl`/`lst`/`eq`/`thm`.
- No I/O in tmark: URLs, file reads and nav order are the plugin's.
- The web contract holds: `tests/test_counters_mkdocs.py` asserts
  `id="fw:watchdog">FW-01` and `<a href="findings/#fw:watchdog">FW-01</a>`;
  the `HtmlReader` reads `figure/figcaption`, `ts-counter`, `ts-index`,
  `data-ts-table`. Keeping those shapes keeps the tests and keeps
  `texsmith page.html` valid on a lowered site (R9).

## Options considered

**(a) Lower in `on_page_markdown`, let Material render.** tmark parses the
page, resolves it with site-wide numbers, and prints back Markdown plus
HTML fragments the standard extension set (spec Table `tbl:extensions`)
understands. Re-printing the whole document under `Profile::Mkdocs` breaks
mkdocstrings and rewrites every byte the printer normalises (bullets, table
alignment, fence lengths, quoting). Splicing only the constructs that need
it, every other byte untouched, is what `04-printer.md` §Local edits
already defines. Chosen, as splices.

**(b) tmark's HTML writer for the page body.** Drops Material's extension
set and the `toc` tree `page.toc` is built from; only the LSP preview wants
it. Rejected.

**(c) A small Python-Markdown extension for the residue.** After (a) the
residue is empty: every construct lowers to class C/E Markdown or to HTML
the standard set passes through (`md_in_html`, `attr_list`). The plugin
injects those extensions when absent, as the counters plugin does today.
Rejected: it would keep `markdown` a runtime dependency for nothing.

**PDF input.** Page source through tmark (D5), not `page.content` through
the `HtmlReader`: one registry numbers both media, `media=print`, raw LaTeX,
index entries and asides survive, no bs4 reverse-engineering of Material
HTML. The `HtmlReader` stays as a *per-page fallback* (`press.reader: html`
in page meta) for pages other extensions generate (mkdocstrings API pages);
both readers produce the generated models, so a book may mix them.

## Recommendation

One plugin, `texsmith`, two media, one registry, one spelling table.

1. **Pre-pass (`on_nav`)**: for every page in nav order (then pages outside
   the nav, file order) `tmark.parse` the source, `tmark.resolve` with
   `numbering="all"` and `start` chained from the previous page's
   `next_start`; keep the IR; build the site label map
   `key → {page src, number, prefix, kind, title}`.
2. **Lowering (`on_page_markdown`, late priority so `macros` runs first)**:
   `tmark.resolve` again with `book` = the site map minus this page,
   locations relativised by the plugin (`findings.md#fw:x`, which MkDocs
   rewrites to the final URL itself), then `tmark.lower_web(text, doc,
   resolved, opts)` → Markdown with local splices. The input text is stored
   for the PDF build. Bytes outside a recognised construct are never
   touched: mkdocstrings, tabs, icons, critic, `!!!` callouts and custom
   fences pass through.
3. **Search (`on_page_content`, `on_post_build`)**: the lunr injection of
   `IndexPlugin` moves into the plugin unchanged; it scans HTML.
4. **PDF (`on_post_build`)**: books are built from the stored sources
   through the CLI pipeline (parse → passes → `resolve` seeded with the
   *same* chained `start` as the site → `write latex`), so `FW-10` is
   `FW-10` on both media whatever section a book covers. Backend series stay
   LaTeX-numbered in print; only the web asks tmark to number them.
5. **Assets**: the plugin ships `texsmith.css` (aside, subfigure grid,
   caption label, counter span) through `extra_css`.
6. **Deleted**: `extensions/counters/mkdocs_plugin.py`,
   `extensions/index/mkdocs_plugin.py` (entry points kept one release as
   warning aliases), every Markdown extension.

`Profile::Mkdocs` stays a *spelling table* (roles → PyMdownX sugar, `:::`
callouts → `!!!`/`???`, `{include}` → `--8<--`) used by `tmark fmt
--profile mkdocs` for the D0 bridge. `lower_web` uses the same table for
the text of each replacement and adds what a profile cannot: numbers,
targets, HTML wrappers. Two entry points, one table, no drift.

## Per-construct behaviour table

*verbatim* = bytes untouched; *sugar* = `Profile::Mkdocs` spelling; HTML
goes through `md_in_html`/`attr_list`. Numbers come from `Resolved`;
`{name} {number}` is the counter's `ref` template, localised by `lang`.

| Construct | Web lowering | PDF (source path) |
| --------- | ------------ | ----------------- |
| `#(fw:x)`, `{counter}(fw:x)` | `<span class="ts-counter" id="fw:x" data-counter="fw" data-key="x">FW-10</span>` | writer |
| `## T {#fw:x}` (silent item) | verbatim; number allocated, no text | writer |
| `@fw:x`, `@fig:x`, `@[fig:a; fig:b]` local | `[FW-10](#fw:x)`, `[Figure 3](#fig:x)`, `[figures 3 and 4](#fig:a)`; capitalised prefix honoured | `\ref` |
| `@key` defined on another page (`Resolution::Sibling`) | `[FW-10](other.md#fw:x)` | `\ref` (same book) or `[?key]` |
| `@sec:x` | `[Heading title](#sec:x)` (Material numbers no sections); `opts.sections="number"` gives `section 2` | `\ref` |
| `[text](#id)` textual ref | verbatim (`refs.textual.web` is `{text}`) | `.print` template |
| `@alias:key` (inventory) | plain text `RHE-423-FW-10 p. 14`, no link | same |
| `@ein05`, `@[ein05, p. 33]`, `@doi:…` | `<a class="ts-cite" href="#ref-ein05">…</a>` in the HTML writer's built-in author-year style, plus a `References` list appended from `Resolved.bibliography`; unresolved DOI → link to doi.org; `opts.citations="passthrough"` emits Pandoc `[@key]` for `mkdocs-bibtex` sites | `\cite`, CSL |
| `@gls:term` | `<abbr title="definition">term</abbr>` (Material tooltip) | glossary macro |
| `[?key]` unresolved | `[?key]` literally, diagnostic | same |
| `![a](f.png){#fig:x}` + `Figure: c {#fig:x}` (before or after) | `<figure markdown="span" id="fig:x">` image verbatim `<figcaption markdown="span"><span class="ts-caption-label">Figure 3:</span> c</figcaption></figure>` | `figure` |
| `::: figure {cols=2}` … `Figure:` | same wrapper, `class="ts-subfigures" style="--ts-cols:2"`, `(a)`, `(b)` under each image; `@fig:crash` → `figure 3b` | `subfigure` |
| pipe table + `Table:` line | `<figure markdown="1" class="ts-table" id="tbl:x"><figcaption>Table 2: c</figcaption>` table verbatim `</figure>`; a `table-config` fence is dropped (print concerns) | `tabularx` |
| `yaml table` fence | `<table class="ts-table" data-ts-table …>` with `<td markdown="span" colspan rowspan>` cells in `Mkdocs` spelling; `table-config` consumed; caption wrapper as above | table model |
| code fence + `Listing:` line | `<figure markdown="1" class="ts-listing" id="lst:x">` fence verbatim `<figcaption>Listing 1: c</figcaption></figure>` | `tscode` |
| `$$ … $$ {#eq:x}` | math verbatim inside `<div id="eq:x" class="ts-equation" markdown="1">`; `@eq:x` → `[equation 2](#eq:x)` | `\label` |
| `!!! type "T"`, `??? type` | verbatim | callout |
| `::: type {title=…}` | sugar `!!! type "T"`, body re-indented, inner splices applied; `collapsed` → `???`/`???+` | callout |
| `::: theorem {#thm:x}` (numbered kind, or any id) | `<div class="admonition theorem" id="thm:x" markdown="1"><p class="admonition-title">Theorem 3 (T)</p>…</div>`, `<details>` when collapsed (`!!!` has no id syntax) | numbered callout |
| `::: aside`, `{aside side=left}[…]` | `<aside class="ts-aside" data-side="left" markdown="1"` (block) or `"span"` (inline) `…</aside>` | `\marginnote` |
| `{index}[a][b]`, `#[a]`, `#[**a**]` | `<span class="ts-index" data-tag="a" data-tag1="b" data-registry="r" data-main></span>`, zero width | `\index` |
| `{sc}[x]`, `__x__` | `<span class="ts-smallcaps">x</span>` (Python-Markdown would bold `__x__`) | `\textsc` |
| `{keys}`, `{mark}`, `{del}`, `{sub}`, `{sup}`, `{code py}` | sugar `++k++`, `==x==`, `~~x~~`, `~x~`, `^x^`, `` `#!py x` `` | writer |
| `{underline}[x]`, `[x]{#id .c lang=fr}` | `<u>x</u>`, `<span id class lang>x</span>` (no anonymous span in Python-Markdown) | writer |
| `{raw html}(…)`, `html raw` / `{raw latex}(…)`, `latex raw` | payload verbatim / removed, whitespace collapsed | dropped / passthrough |
| `media=print` / `media=web` | removed / unwrapped, attribute list stripped | reverse |
| `{include}(f)` / `--8<-- "f"` | replaced by the lowered text of `f` (own spans, own labels) / verbatim for `snippets`, `deprecated` diagnostic | include pass |
| `{{ key }}` (`Var`) | front-matter value; unknown keys verbatim (`macros` ran first) | `var` pass |
| `mermaid` fence, `![](x.drawio)`, ```` ```md {.snippet} ```` | verbatim (Material, the `drawio` plugin and today's `on_post_page` snippet rewriting render them) | `assets`, `snippet` passes |
| `---`, `Quoted`, footnotes, def lists, `*[ABBR]:`, task and fancy lists, critic, progress bars, tabs, icons, emoji, HTML blocks, comments | verbatim | writer / M5 |
| `::: unknown`, unclosed containers (mkdocstrings) | verbatim, inner splices still applied; `container-unknown` at `info` for dotted names | `Div` |

## Interfaces

What tmark exposes (Rust in the facade, mirrored one-to-one by `tmark-py`):

```rust
// tmark-registry (existing fields kept)
pub struct ResolveOptions { pub numbering: Numbering /* Backend | All */, pub lang: Option<String>,
                            pub book: Vec<BookLabel> /* labels of sibling documents */, … }
pub struct BookLabel { pub key: String, pub prefix: String, pub number: Option<String>,
                       pub kind: Host, pub title: Option<String>, pub location: String }
pub enum Resolution { …, Sibling { label: String, location: String } }   // a local definition wins
impl Resolved { pub fn next_start(&self) -> BTreeMap<String, u32>;       // feeds the next document's `start`
                pub fn book_labels(&self, location: &str) -> Vec<BookLabel>; }
// tmark-fmt
pub fn edit_many(text: &str, doc: &Document, edits: Vec<NodeEdit>) -> String;   // batch splice, disjoint spans
pub fn format(doc, Profile::Mkdocs)                                             // the spelling table, made real
// tmark-writers::mkdocs, re-exported by the facade
pub struct WebOptions { pub sections: SectionRefs /* title | number */, pub citations: Citations /* inline | passthrough */,
                        pub lang: Option<String>, pub css_prefix: String /* "ts-" */ }
pub fn lower_web(text: &str, doc: &Document, res: &Resolved, loader: &dyn Loader, opts: &WebOptions) -> Lowered;
pub struct Lowered { pub text: String, pub diagnostics: Vec<Diagnostic>, pub bibliography: Option<String> }
```

```python
tmark.resolve(doc, loader, options) -> dict     # "labels", "refs", "counters", "next_start", "diagnostics"
tmark.lower_web(text, doc, resolved, loader, options) -> dict   # {"text", "diagnostics", "bibliography"}
```

`lower_web` walks the tree, emits one `NodeEdit` per construct of the table
and calls `edit_many`; replacement text is printed with `Profile::Mkdocs`
for children that need no lowering and recursively otherwise, re-indented
by `Out`. Included files come from `Resolved.included` plus the `Loader`
for their text. It is pure: locations are opaque strings.

What the plugin calls, in order: `on_config` (inject `attr_list`,
`md_in_html`, `admonition`, `pymdownx.details`, `pymdownx.superfences` if
absent; register `texsmith.css`; read `declare.counters` from `mkdocs.yml`)
→ `on_nav` (parse, chained resolve, site map, keep IR) → `on_page_markdown`
at `event_priority(-50)` (resolve with `book`, `lower_web`, store source)
→ `on_page_content` (collect `ts-index` tags) → `on_post_page` (snippet URL
rewriting, unchanged) → `on_post_build` (lunr injection; books from stored
sources: passes, `resolve` seeded by the site chain, `write`, `Requires` →
fragments, template wrap, engines). A page with `press.reader: html` is
captured as `page.content` and read by the `HtmlReader` into the same
models; its labels still come from the tmark pre-pass, best effort.

## Work items

tmark, ordered:

1. `Profile::Mkdocs` spelling table in `tmark-fmt` (plan 1.7); snapshots on
   the fixture corpus. Unblocks the D0 bridge.
2. `edit_many`; property test: splicing every node with itself is identity.
3. `ResolveOptions.numbering`, `lang`, `Resolved::next_start`. Web scope is
   `document` (continuous across the site through `start`).
4. `ResolveOptions.book`, `BookLabel`, `Resolution::Sibling`,
   `Resolved::book_labels`; siblings never shadow a local key.
5. `tmark-writers::mkdocs::lower_web`, one function per table row, snapshot
   per fixture; a required fixture is `::: a.b` unclosed followed by prose
   with `@` refs (the mkdocstrings case).
6. `tmark-py`: `resolve` returning the dict above, `lower_web`, `Loader`
   wrapped (plan 2.1 already adds `resolve`).
7. `container-unknown` at `info` for dotted names; `tmark lower FILE --to
   web` for debugging.

TeXSmith, ordered:

1. `mkdocs_plugin_texsmith`: pre-pass and site map on `tmark.parse` +
   `tmark.resolve` (replaces the regex pre-pass of `counters/mkdocs_plugin.py`),
   `on_page_markdown` lowering, `texsmith.css`, extension injection. Behind
   the phase-3 `--reader tmark` flag until the flip. `tests/test_counters_mkdocs.py`
   ported with its assertions unchanged; figure, table, index, aside and
   callout cases added to `tests/test_mkdocs/docs`.
2. Lunr injection moved from `index/mkdocs_plugin.py` into the plugin;
   `texsmith.counters` and `texsmith.index` become warning aliases, removed
   in 0.8.
3. PDF path from stored sources (plan 3.9): per-book `resolve` seeded by the
   site chain; `press.reader: html` fallback through the retargeted
   `HtmlReader` (3.8), which learns `ts-aside`, `ts-smallcaps`,
   `ts-caption-label` and the `ts-table` figure wrapper.
4. `examples/mkdocs` gains a page exercising every table row;
   `docs/guide/mkdocs.md` and `docs/syntax/counters.md` §"On a MkDocs site"
   rewritten: one plugin, no extensions, `declare.counters` in `mkdocs.yml`.
5. Phase 5: delete the two MkDocs plugins with the extensions.

## Open questions

1. **Chapter-scoped numbering on the web.** The `book` template numbers
   figures `3.2`; the site would show `Figure 12`. A `numbering: chapter`
   mode using the top-level nav section as chapter is possible but couples
   numbers to the nav shape. Start with `document`; revisit on a real site.
2. **Dotted container names.** Spec challenge: `::: a.b` is a foreign
   directive, verbatim, closed by the next dedent, no diagnostic. Removes
   the only known collision with the MkDocs ecosystem.
3. **`md_in_html` span mode on `<td>`.** The yaml-table row relies on
   `markdown="span"` on cells; verify on the test site before tmark item 5,
   else render cell inlines to HTML in the lowering.
4. **Where `lower_web` lives.** Rust, so Zensical and the LSP preview reuse
   it and escaping is not duplicated; the cost is R7 (a tmark release per
   fix). A Python splicer over the JSON spans is a viable stop-gap if the
   cadence hurts in phase 3: the IR carries every span, `Resolved` every number.
5. **Macro-generated labels.** The pre-pass reads raw sources, so a label a
   macro produces is numbered only if it reaches the lowering. Documented
   limitation, as with today's regex pre-pass.
6. **Bibliography on the web.** Built-in author-year only; `mkdocs-bibtex`
   sites use `citations: passthrough`. CSL on the web is not planned.

## Closing note — what shipped

The recommendation was taken whole: one `texsmith` MkDocs plugin renders the
site and exports the PDF, and `lower_web` is Rust. `on_nav` pre-passes every
page with `tmark.parse` + `tmark.resolve(numbering="all")`, `start` chained in
navigation order, and builds the site label map; `on_page_markdown` resolves
each page against that map minus its own labels and splices its constructs with
`tmark.lower_web`; `on_post_build` builds every book from the stored sources
through the same reader path the CLI uses, seeding one `ResolutionChain` where
the site's chain stood before the book's first page. `mkdocs.yml` needs no
Markdown extension of its own — `on_config` turns on the five the lowering
relies on when they are absent — and `assets/texsmith/texsmith.css` ships the
shapes the lowering emits. `examples/mkdocs` exercises every row of the
per-construct table.

The two old plugins are deprecated aliases that log a warning and do nothing;
they are removed in 0.8. A page that still wants the Python-Markdown rendering
sets `press.reader: html` in its front matter and goes through
`Document.from_html(page.content)` — the escape hatch the *reader* keeps now
that the CLI has no `--reader` option.

Of the open questions: (2) dotted container names are read as foreign
directives, closed by the next dedent, which removes the collision with the
MkDocs ecosystem. Still open: (1) chapter-scoped numbering on the web (the site
shows `Figure 12` where the `book` template prints `3.2`); (3) `md_in_html`
span mode on `<td>`; (5) labels a macro generates, which the pre-pass reading
raw sources cannot see; (6) bibliography on the web, still author-year only.
