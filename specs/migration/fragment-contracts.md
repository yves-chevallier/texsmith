# Fragment contracts — what replaces the Jinja partials (D3, R2)

Status: proposal, 2026-09-11. Settles decision D3 and difficulty R2 of
`specs/tmark-migration.md` and delivers the `FRAGMENTS` table that
`~/tmark/design/07-writers.md` places in `tmark_ir::registry`.

## 0. Findings that shape the triage

- The writer calls 45 of the 55 partials; ten are orphans (no
  `render_template` call in `src/`): `acronym`, `add`, `del`, `glossary`,
  `include`, `list_acronyms`, `list_glossary`, `tabbed`, `url`, `exercises_solutions`.
- Partials name macros no bundled fragment defines: `goodbox`/`commentbox`
  exist nowhere; `\epigraph` and `multicols` load only in `book`; `\uline`
  needs `ulem`, which `ts-extra` adds only when it sees `\sout{`. A contract
  fixes this by construction: a macro the writer names, a fragment must define.
- `highlight.tex` and `lead.tex` put preamble logic (`\providecommand`, an
  engine conditional) in the body. Activation is string sniffing over the
  rendered LaTeX (`\begin{callout`, `\keystroke{`, `\done`, `\begin{code`)
  plus `DocumentState` flags.
- The only bundled override is `book` → `codeblock.tex`, `codeinline.tex`
  (drops `breaklines`). Nothing bundled uses `required_partials`, `readers`
  or `writer`.

## 1. Triage of the 55 partials

**W** structural LaTeX from the writer (packages in `Requires.packages`);
**C** contract macro/environment from a named fragment
(`Requires.fragments`); **T** template-level partial; **X** dropped. Typst:
`#ts-…` lives in a shared `texsmith.typ` copied next to the `.typ` (today
each construct is inlined per instance).

| Partial | → | Macro / environment and signature | Fragment | Packages | Typst |
| --- | --- | --- | --- | --- | --- |
| italic, strong, smallcaps, subscript, superscript | W | `\emph`, `\textbf`, `\textsc`, `\textsubscript`, `\textsuperscript` | — | — | `_x_`, `*x*`, `#smallcaps`, `#sub`, `#super` |
| strikethrough, underline | W | `\sout{…}`, `\uline{…}` | — | `ulem[normalem]` | `#strike`, `#underline` |
| enquote | W | `\enquote{…}` | — | `csquotes` | `"…"` |
| blockquote | W | `\begin{displayquote}…\end{displayquote}` | — | `csquotes` | `#quote(block: true)[…]` |
| highlight | C | `\tsmark{…}` (engine conditional moves into the fragment) | ts-typesetting | `xcolor`; `soul` \| `lua-ul` per engine | `#highlight[…]` |
| lead | C | `\tslead{…}` (`Para.lead`) | ts-typesetting | — | `#ts-lead[…]` |
| horizontal_rule | C | `\tsdivider` (default `\clearpage`; spec: "paged templates render `\clearpage`") | ts-typesetting | — | `#ts-divider()` → `#pagebreak()` |
| epigraph | C | `\tsepigraph[source={…}]{…}` (`BlockQuote{.epigraph}`, front-matter `epigraph:`) | ts-typesetting | `epigraph` | `#ts-epigraph(source:)[…]` |
| multicolumn | C | `\begin{tsdiv}{multicolumn}[cols=2]…` (generic container contract, §3) | ts-typesetting | `multicol` | `#ts-div("multicolumn", cols: 2)[…]` → `#columns` |
| tabbed | C | `\begin{tsdiv}{tab}[title={…}]…`; default: bold title + content | ts-typesetting | — | `#ts-div("tab", title:)[…]` |
| icon | C | `\tsicon{path}` (emoji artifact mode; `Image{.icon}` from the emoji pass) | ts-typesetting | `graphicx` | `#box(image(..), height: 1em)` |
| counter | W | `\leavevmode\phantomsection\label{id}text` (`CounterItem`, resolved text) | — | `hyperref` | `text<id>` |
| label | W | `\phantomsection\label{id}` (span `{#id}`) | — | `hyperref` | `<id>` |
| ref | W | `\hyperref[id]{text}` / `\ref{id}` (label template from resolution) | — | `hyperref` | `#link(<id>)[…]` / `#ref(<id>)` |
| href, url | W | `\href{url}{text}`, bare autolink `\url{url}` | — | `hyperref` | `#link("url")[…]` |
| footnote | W | `\footnote{…}` | — | — | `#footnote[…]` |
| citation | W | `\cite{k1,k2}`, `\cite[post]{k}`, `\parencite`/`\textcite` per `RefItem`; `Requires.bibliography=true` | ts-bibliography provides `\parencite`/`\textcite` fallbacks when no `.bib` | `biblatex` (with `.bib`) \| `thebibliography` | `#cite(<k>)` |
| acronym, glossary | C | `\tsgls{key}` = `\gls` (first use expands, the author writes the call); `Abbr` → `\tsacr{key}` = **`\acrshort`**, the short form wherever it stands — decision O5, `parity-triage.md` §6 | ts-glossary | `glossaries[acronym]` | `#ts-gls(key)` → text, `#ts-acr(key)` → key |
| list_acronyms, list_glossary | T | orphans; `ts-glossary.sty` already generates `\newacronym`/`\newglossaryentry` from `Document.abbreviations` + front matter | ts-glossary | — | `acronyms` slot (exists) |
| index | C | `\tsindex[registry=r, main]{sort@formatted!sub}` (zero-width; `Requires.index` lists registries) | ts-index | `imakeidx` | `#ts-index(..)` no-op (open question 6) |
| keystroke | C | `\tskeys{Ctrl,Alt,Del}` (label table `KEY_LABELS` shared by writers in `common.rs`; a literal comma is braced) | ts-keystrokes | `tikz` | `#ts-keys("Ctrl","Alt")` |
| choices | C | `\begin{tstasklist}` with `\item[\tsdone]`, `\item[\tstodo]`, `\item[\tspartial]` (`ListItem.task`) | ts-todolist | `enumitem`, `amssymb`, `pifont` | `#ts-task(state)[…]` |
| unordered_list, ordered_list | W | `itemize`, `enumerate` (`start` → `\setcounter`, `style` → `enumitem` label) | — | `enumitem` when `style`/`start` | `- …`, `+ …`, `#enum(numbering:)` |
| description_list | W | `\begin{description}\item[{term}] …` | — | — | `/ term: …` |
| heading | W | `\part`…`\subparagraph`, `*` when unnumbered, `\label`, `\mbox{}\\` for levels ≥ 4; level offset applied by the `headings` pass, never an option | — | — | `= … <id>` |
| pagestyle | X | `\thispagestyle{plain}` stood where the promoted title was; the template emits it after `\maketitle` | — | — | — |
| figure | W | `figure[H]`, `\centering`, `\includegraphics[width=…]` (`NN%` → `0.NN\linewidth`), optional `\href`, `\caption[short]{…}` **then** `\label`; `adjustbox` guard | — | `graphicx`, `float`, (`adjustbox`) | `#figure(image(..), caption:)<id>` |
| figure_tcolorbox | W | inside a `tscallout`/`tscode` box the writer knows it is in a box and emits `center` + `\captionof{figure}` (no float in a box) | — | `caption` | same `#figure` |
| table, yaml_table | W | `table`/`center` + `tabularx`\|`tabular`\|`longtable`, `booktabs` rules, `multirow`/`multicolumn`, placement, `\caption` then `\label`, the `\tabcolsep` discount | — | `booktabs`, `tabularx`, `longtable`, `multirow`, `float` | `#table`, `#figure(table(..))` |
| callout | C | `\begin{tscallout}[kind=note, title={…}, id=x, collapsed]…\end{tscallout}` | ts-callouts | `tcolorbox`, `xcolor` | `#ts-callout(kind:, title:)[…]` |
| codeblock, codeblock_listings, codeblock_verbatim, codeblock_pygments | C | `\begin{tscode}[lang=py, title={…}, linenums=1, hl_lines={2-3,7}, id=x]…\end{tscode}` (§5) | ts-code | `tcolorbox`, `fvextra` + `minted` \| `listings` per engine | ```` ```py ```` fence, `#ts-code(..)` for title/lines |
| codeinline, codeinlinett | C | `\tscodeinline[lang=py]{escaped text with \allowbreak{}}` (§5) | ts-code | — | `` `x` `` |
| add, addition | C | `\tsins{…}` | ts-critic (new) | `ulem`, `xcolor` | `#ts-ins[…]` |
| del, deletion | C | `\tsdel{…}` | ts-critic | `ulem` | `#ts-del[…]` |
| substitution | C | `\tssubst{old}{new}` | ts-critic | `ulem` | `#ts-subst[old][new]` |
| comment | C | `\tscomment{…}` | ts-critic | `xcolor` | `#ts-comment[…]` |
| regex | X | Material helper, not a construct: `Link{Code}` renders `\href{…}{\tscodeinline{…}}` by composition | — | — | `#link(..)[`…`]` |
| include | W | `\input{stem}` for an `Include` TeXSmith did not splice (design 07) | — | — | `#include "stem"` |
| exercises_solutions | T | orphan French exam scaffolding; stays a template partial (delete from core, move to the template that wants it) | — | — | — |

Emitted with no partial today: `Aside` → `\tsaside[side=left]{…}` (ts-typesetting,
`marginnote`; the `\marginfont`/`\marginparwidth` clamp of `ts-extra` moves
there); `ProgressBar` → `\tsprogress[thin]{0.45}{label}` (ts-typesetting,
`progressbar`); `Span{script=slug}` → `\tsscript{slug}{…}`, font-mode emoji →
`\tsemoji{…}` (ts-fonts); `Div{name}` without a rule → `tsdiv`, transparent. Math, `RawBlock`, `Comment`, `Var`: nothing.

## 2. The `FRAGMENTS` table (`crates/tmark-ir/src/registry.rs`)

```rust
/// One row of the fragment-contract table. Design 07-writers.md: the writer
/// names the contract in `Requires.fragments`; TeXSmith's fragment defines the
/// macros. Names are the `press.fragments` spellings.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct Fragment {
    pub name: &'static str,
    /// Macros (`\` prefix) and environments (bare) the fragment must define.
    pub provides: &'static [&'static str],
    /// LaTeX packages the contract implies; merged into `Requires.packages`
    /// so `tlmgr` hints and `ts-extra` see them. What the fragment actually
    /// loads is its own business.
    pub packages: &'static [&'static str],
    /// The contract needs `-shell-escape` regardless of options.
    pub shell_escape: bool,
    pub description: &'static str,
}

const fn frag(name: &'static str, provides: &'static [&'static str],
              packages: &'static [&'static str], description: &'static str) -> Fragment
{ Fragment { name, provides, packages, shell_escape: false, description } }

pub const FRAGMENTS: &[Fragment] = &[
    frag("ts-typesetting",
         &["\\tslead", "\\tsmark", "\\tsdivider", "\\tsepigraph", "\\tsaside",
           "\\tsprogress", "\\tsicon", "tsdiv"],
         &["xcolor", "epigraph", "marginnote", "multicol", "progressbar", "graphicx"],
         "lead-ins, highlight, divider, epigraph, asides, progress bars, generic containers"),
    frag("ts-callouts", &["tscallout"], &["tcolorbox", "xcolor"], "admonitions and theorem boxes"),
    frag("ts-code", &["tscode", "\\tscodeinline"], &["tcolorbox", "fvextra"],
         "code listings; engine (minted/listings/verbatim/pygments) is the fragment's choice"),
    frag("ts-keystrokes", &["\\tskeys"], &["tikz"], "keyboard keys"),
    frag("ts-todolist", &["tstasklist", "\\tsdone", "\\tstodo", "\\tspartial"],
         &["enumitem", "amssymb", "pifont"], "task lists"),
    frag("ts-glossary", &["\\tsgls", "\\tsacr"], &["glossaries"], "glossary terms and acronyms"),
    frag("ts-index", &["\\tsindex"], &["imakeidx"], "index entries and registries"),
    frag("ts-bibliography", &["\\parencite", "\\textcite"], &[], "citation fallbacks without biblatex"),
    frag("ts-fonts", &["\\tsscript", "\\tsemoji"], &["fontspec"], "script and emoji font switches"),
    frag("ts-critic", &["\\tsins", "\\tsdel", "\\tssubst", "\\tscomment"], &["ulem", "xcolor"],
         "critic markup (tmark M5)"),
];

pub fn fragment(name: &str) -> Option<&'static Fragment> { FRAGMENTS.iter().find(|f| f.name == name) }
```

`shell_escape` is `false` on every bundled row: `ts-code` needs it only for
`minted`, and the writer sets `Requires.shell_escape` from
`WriterOptions.code.engine` (07-writers); the field serves third-party
contracts that always shell out. A test asserts `provides` entries are unique
across rows; `tmark-py` exposes the table as `tmark.fragments()`.

**Activation in TeXSmith** (`core/fragments/resolution.py`; replaces the
`should_render` sniffers and the `DocumentState` flags):

| Fragment | Active when | Replaces |
| --- | --- | --- |
| any row of `FRAGMENTS` | `name in Requires.fragments` | `_detect_callouts`, `_detect_keystrokes`, `_detect_todolist`, `_detect_code`, `callouts_used` |
| ts-index | `Requires.index` non-empty; registries → `\makeindex[name=…]` | `has_index_entries`, `index_entries`, `index_terms`, `has_index` |
| ts-bibliography | `Requires.bibliography`; cited keys from `Resolved` feed the `thebibliography` fallback | `citations`, `record_citation`, `bibliography_entries` |
| ts-glossary | in `Requires.fragments` or front-matter `glossary`/`acronyms`; entries from `Document.abbreviations` (the `glossary` pass) | `abbreviations`, `acronyms`, `acronym_keys`, `remember_abbreviation` |
| ts-fonts | always (config); the `scripts` pass summary says which `\text<slug>` to declare | `script_usage`, `fallback_summary` |
| ts-code | as row one; `pygments_style_defs` from the `highlight` pass result | `pygments_styles`, `requires_shell_escape` (→ `Requires.shell_escape or template.shell_escape`) |
| ts-extra | always; packages = `Requires.packages` ∪ implied packages of active rows; the string sniffing is deleted | `ts_extra_packages` detection |
| ts-geometry, ts-frame | unchanged (config, not contracts) | — |

`DocumentState.snippets` belongs to the `assets` pass, `headings` to
`Resolved`, `footnotes` to the writer. A `press.fragments` entry not in
`FRAGMENTS` renders unconditionally, as today (custom `.jinja.sty`).

## 3. Naming conventions for contract macros

1. **Prefix and case.** Macros `\ts<name>`, environments `ts<name>`,
   lowercase, no digits, one word per construct. The `\texsmithCamelCase`
   internals (`\texsmithHighlight`, `\texsmithEmoji`, `\texsmithCalloutIcon`)
   are not contracts: nothing outside a fragment names them; the two the
   writer used become `\tsmark` and `\tsemoji`.
2. **Argument order.** At most one optional keyval group first, then the
   mandatory arguments, content last: `\tsepigraph[source={…}]{text}`,
   `\begin{tscallout}[kind=note, title={…}]`. Only `tsdiv` takes a mandatory
   argument before the keys, the container name, so `\csname
   tsdiv@name\endcsname` dispatch is trivial. A third mandatory argument
   means a key is missing.
3. **Keyval for options**, parsed with `pgfkeys` under `/ts/<name>/`
   (tcolorbox and tikz load it; `l3keys` where neither is loaded). Every
   family ignores unknown keys (`.unknown/.code`), so an older fragment
   survives a newer writer. Definitions use `\NewDocumentCommand` with `O{}`.
4. **Serialisation.** Only keys with a value, in registry order then `id`
   then attrs. Booleans bare (`linenums`, `collapsed`); numbers, identifiers
   and lengths verbatim (`width=40%` becomes `0.4\linewidth` only for
   structural `\includegraphics`, never inside a key); text (`title`,
   `source`) escaped and braced; lists braced with commas (`hl_lines={2-3,7}`).
5. **Identity.** Structural output: the writer emits `\label`. Contract output:
   the writer passes `id=`; the fragment places `\phantomsection\label` (tcolorbox `label=`).
6. **Attrs on a container.** `::: warning {#w1 .wide cols=2 title="…"}` →
   `\begin{tscallout}[kind=warning, id=w1, class={wide}, cols=2, title={…}]`:
   `#id` → `id`, classes → `class={a,b}` (styled with
   `/ts/callout/class/wide/.style`), `key=val` forwarded as is, node fields
   win over attrs of the same name; `lang` and `media` are never forwarded.
7. **Typst symmetry.** One hyphenated function per contract (`#ts-callout`,
   `#ts-keys`), named arguments mirror the keys, content last; `texsmith.typ`
   is copied next to the `.typ` and a template overrides after importing it.

## 4. Overriding a construct after the change

Macro redefinition in the template's `.tex`, after `\VAR{extra_packages}`
(fragments are `\usepackage`d there):

```latex
\VAR{extra_packages}
% Book: inline code without break opportunities, listings without frame.
\RenewDocumentCommand{\tscodeinline}{O{}m}{\texttt{#2}}
\tcbset{/ts/code/.append style={frame hidden, boxrule=0pt}}
\RenewDocumentEnvironment{tsdiv@multicolumn}{O{}}{\begin{multicols}{3}}{\end{multicols}}
```

Three levels, documented in `docs/guide/templates/partials.md` (renamed
"Contract macros"): (a) restyle through the pgfkeys family; (b) redefine the
macro, same signature; (c) replace the fragment (`press.fragments:
{disable: [ts-code], append: [./my-code.sty]}`) — the replacement must
define every `provides` entry, checked against `tmark.fragments()` at load
time (the successor of `required_partials`). `book`'s override becomes
(a)+(b); `letter`'s private `callouts.jinja.sty` replaces `ts-callouts` via (c).

Deprecated in 0.7.0 (warning, ignored), removed in 0.8.0:

- `latex.template.override` and fragment `partials`: the warning names the
  replacement macro per partial (§1 is the mapping).
- `required_partials` (templates and fragments): replaced by the `provides` check.
- `[latex.template] readers` / `writer` (0.4.1): `@reads` goes with the HTML
  main path, `@writes` with the Python writer. Custom constructs are
  `::: name` containers rendered by `tsdiv` (a `\tsdiv@name` definition in
  the template) or, when they compute, a Python IR pass declared under
  `[latex.template] passes = ["pkg.module:pass"]` (`Document → Document`).

Changelog text (0.7.0, "Deprecated"):

> **Jinja partials are no longer the rendering layer.** LaTeX and Typst
> bodies come from tmark's writers, which emit a fixed macro per construct
> (`\tscallout`, `tscode`, `\tskeys`, `\tslead`, …) provided by the `ts-*`
> fragments. `latex.template.override`, fragment `partials` and
> `required_partials` are ignored and warn; override a construct by
> redefining its macro in your template (`docs/guide/templates/partials.md`
> maps each former partial to its macro). The template-scoped `readers` and
> `writer` hooks of 0.4.1 are deprecated: custom constructs are `::: name`
> containers rendered by `tsdiv`, or an IR pass declared under
> `[latex.template] passes`. All of these are removed in 0.8.0.

## 5. The code contract in detail

```latex
\begin{tscode}[lang=py, title={bubble\_sort.py}, linenums=1, hl_lines={2-3}, id=lst:bubble, stretch=0.5]
def bubble(xs): ...
\end{tscode}
\tscodeinline[lang=py]{xs\allowbreak{}.sort()}
```

Keys: `lang` (default `text`), `title` (escaped text), `linenums` (bare or
start number), `hl_lines` (ranges), `id`, `stretch` (the ASCII-art
`baselinestretch` heuristic stays in the writer, emitted as a key),
`caption` (escaped text: the `Listing: …` caption line attached to the
fence, spec §Caption; the fragment typesets it as a listing caption and the
`id` is then the listing's anchor, `lst:` series), `engine` (set only by
the pass below); `include=` is consumed by the `include` pass.
The body is verbatim: `tscode` reads verbatim in every engine (tcolorbox
`listing only` over `minted` or `listings`, or `fvextra`'s `Verbatim`), so
the writer emits the source unchanged plus a final newline; today's
`{`→`\{` doubling for minted is dropped. `ts-code` reads `code.engine`
(`pygments` default, `minted`, `listings`, `verbatim`) and defines `tscode`
accordingly, as `ts-code.jinja.sty` does for `code` now; the writer learns
the engine only to set `Requires.shell_escape`. Boxes nest, and the writer
emits `\captionof` for a figure inside one.

**Pygments (and minted inline) are a TeXSmith pass, not a post-process.**
`texsmith/passes/highlight.py` runs after `include`/`var`, LaTeX backend
only. Engine `pygments`: every `CodeBlock` becomes `RawBlock{format=latex}`
holding the whole `\begin{tscode}[…, engine=pygments]…\end{tscode}` with
Pygments' `\PY{…}` body for `Verbatim[commandchars=\\\{\}]`, and every
`Code` becomes `RawInline` `{\ttfamily …}` with `add_break_points`. Engine
`minted`: `Code` only (`\mintinline{lang}|…|`, delimiter choice,
`code.inline.plain`); blocks stay for the fragment. Style definitions are a
pass result handed to `ts-code` (`pygments_style_defs`). Why not
post-process the body: the pass sees typed `options` (no regex over
`\begin{tscode}[…]`, no un-escaping of titles); the source map survives (a
`RawBlock` keeps id and span, a substitution shifts every later offset); it
reuses the `latex raw` path, so nothing in the writer is pygments-specific;
it is unit-testable on IR fixtures; and Python-only work stays in Python
(`00-overview.md`). Cost: HTML/Typst previews never see it (they highlight
natively), and `inline_breaks` exists twice — `WriterOptions.code.inline_breaks`
for `\tscodeinline`, the pass for pygments/minted inline; both read
`code.inline.breaks` (0.6.0).

## 6. Work items and open questions

tmark (phase 1.1, before 1.2): (1) `Fragment`, `FRAGMENTS`, `fragment()` and
`KEY_LABELS` in `registry.rs` with tests; (2) `Requires` unchanged (07-writers
already has every field used here); (3) the LaTeX writer emits the
signatures of §1 and §3, with a `requires` assertion per fixture; (4)
`tmark.fragments()` in `tmark-py`; (5) `texsmith.typ` names fixed in the
Typst writer fixtures.

TeXSmith (phases 3.5–3.6): (6) `highlight` pass; (7) `resolution.py` maps
`Requires` to active fragments, deleting the `_detect_*` sniffers and the
flags of §2; (8) each `ts-*.sty` defines its `provides` (`code`→`tscode`,
`callout`→`tscallout`, `todolist`→`tstasklist`, `\keystroke`→`\tskeys`, the
`ts-typesetting` macros, new `ts-critic`); (9) `book` and `letter` converted
per §4, warnings for `required_partials`/`override`; (10) delete the ten
orphan partials now (no behaviour change), the rest in phase 5; (11) docs:
`partials.md` → contract table, `handlers.md` → "IR passes and containers",
the changelog entry of §4.

Open questions: (1) `KEY_LABELS` in the registry (LSP completion) or
writer-local? (2) `\tsacr{key}`: writer and fragment must compute the same
key; proposal: short form sanitised to `[A-Za-z0-9-]` in `common.rs`,
exposed as `tmark.slug()`. (3) Should `\cite` become `\tscite` so a template
without biblatex can restyle citations? Structural for now. (4) `tsdiv` for
`tab`/`multicolumn` presumes `::: multicolumn` and `::: tab` containers the
spec lacks — spec challenges (gap-audit rows "tabbed", "multicolumn"). (5)
`figure` stays structural; is patching `figure`/`\caption` with standard
LaTeX enough for the poster/exam templates R2 names? (6) Typst index:
`#ts-index` no-op or an `in-dexter` dependency? (7) Should `FRAGMENTS`
carry a `typst: &[&str]` column so `texsmith.typ` is checked like the `.sty`?

## 7. Closing note — what shipped

The triage is implemented. Every `provides` entry of `tmark.fragments()` is a
`\NewDocumentCommand` / `\NewDocumentEnvironment` in its fragment's `.sty`,
with keyval options under `/ts/<name>/` and unknown keys ignored, and
`src/texsmith/templates/common/texsmith.typ` is the Typst mirror with the same
signatures. `activate_from_requires()` replaced the `_detect_*` content
sniffers: a body's `Requires` decides which fragments the preamble loads.
`ts-critic` is new, `book` and `letter` are converted, and
`tests/test_fragment_contracts.py` builds a document exercising every macro —
`test_every_provides_entry_is_defined` is the alarm that fires when a contract
added on the tmark side has no definition here.

Item (10) went further than "the ten orphan partials": phase 5 deleted all 45
files of `adapters/latex/partials/`, `LaTeXFormatter`, `core/partials.py` and
the four override hooks (`latex.template.override` and a template's
`overrides/`, template and fragment `required_partials`, a fragment's
`partials`, and the template-scoped `readers` / `writer` of 0.4.1). They are
not deprecated: they are not read at all. Overriding a construct is redefining
its macro after `\VAR{extra_packages}`, which `docs/guide/templates/partials.md`
documents partial by partial.

Of the open questions: (1) `KEY_LABELS` lives in the registry, reachable as
`tmark.registries()["key_labels"]`; (4) the `::: tabs` / `::: tab` and
`::: multicolumn` containers the spec lacked were added, so `tsdiv` has real
sources; (5) `figure` stayed structural. Still open: (2) the acronym key
sanitisation is not exposed as a shared `tmark.slug()`, so the writer and the
fragment agree by convention rather than by construction; (3) `\cite` is still
structural, not `\tscite`; (6) `#ts-index` is a no-op in Typst, awaiting a
decision on an `in-dexter` dependency; (7) `FRAGMENTS` has no `typst:` column,
which is why `texsmith.typ` and the crate's `assets/texsmith.typ` are two
hand-kept copies (`status.md`, "Known duplication").
