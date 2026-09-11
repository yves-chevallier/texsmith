# Writers in Rust, passes in Python, and the parity harness

Status: design note, 2026-09-11. Covers R1, R4, R12 and task 4.1 of
`../tmark-migration.md`. Line references are to the `tmark-migration`
branch of TeXSmith and to `~/tmark` `main`.

## 1. `tmark-writers`

### Layout

```text
crates/tmark-writers/src/
  lib.rs          Writer trait, Backend, WriterOptions, Body, Requires, SourceMap, write(doc, res, opts)
  common/out.rs   Out buffer: tmark-fmt::out::Out plus begin(NodeId)/end(NodeId) that push SourceMap entries
  common/zero.rs  zero-width collapse over &[Inline] (spec §Attributes): shared post-pass, see §2 "zero-width"
  common/media.rs skip(node, medium): attrs.media() != backend medium → node and its whitespace vanish
  common/refs.rs  Resolution → text: counter `ref` template, `[?key]`, textual print/web templates; text.rs: shared Unicode tables (dashes, quotes, sub/superscript)
  latex/{mod,escape,inline,block,table,figure,index,keys}.rs
  typst/{mod,escape,inline,block,table,math,figure}.rs
  html/{mod,escape,inline,block,table}.rs
```

Each backend module is a struct holding `&Document`, `&Resolved`,
`&WriterOptions`, an `Out`, a `Requires` under construction, and the only
mutable context the emitters need (`in_callout` for `\captionof`, `in_cell`,
`list_depth`). Dispatch is `fn block(&mut self, b: &Block)` / `fn inline(&mut
self, i: &Inline)` with an exhaustive `match`, one function per variant, same
names in the three modules (mirrors `tmark-fmt::block::block_with` / `inline::one`):

`str`, `space`, `soft_break`, `line_break`, `emph`, `strong`, `strikeout`,
`underline`, `highlight`, `subscript`, `superscript`, `small_caps`,
`quoted`, `code`, `math`, `link`, `reference`, `note`, `image`,
`index_entry`, `counter_item`, `keystroke`, `aside`, `span`, `var`, `abbr`,
`comment`, `raw_inline`; `para`, `plain`, `header`, `code_block`,
`block_quote`, `bullet_list`, `ordered_list`, `definition_list`,
`horizontal_rule`, `table`, `table_config` (no-op), `caption` (consumed by
the preceding/following `table`/`figure`/`code_block`; alone → diagnostic
`caption-orphan`), `figure`, `admonition`, `div`, `math_block`,
`raw_block`, `include`, `block_comment`. Plus the three helpers every
writer has: `inlines(&[Inline])`, `blocks(&[Block])`, `label(&Attrs)`.

`Div{name}` renders by name: `multicolumn`, `epigraph`, `tabs`/`tab`,
`code` (the highlight pass output, §3), `script` (never: the pass emits
spans), unknown → transparent. Any other name is a fragment macro
`\tsdiv{name}` per D3, not a writer branch.

### `WriterOptions` (derived from `WriterState`, `runtime`, `TypstWriterState`)

| Field | Source today | Note |
| ----- | ------------ | ---- |
| `media: Print \| Web` | design 07 | HTML writer = Web |
| `lang: Option<String>` | front matter | `\foreignlanguage` on spans whose `lang` differs |
| `code.engine: Pygments \| Minted \| Listings \| Verbatim` | `writer.py:633`, `formatter.py:79` | `Pygments` means "expect `Div{code}` from the pass, else fall back to `Verbatim` payload" |
| `code.inline_plain: bool`, `code.inline_breaks: String` | `formatter.py:81-82`, 0.6.0 | `\allowbreak{}` insertion for `\texttt`, `formatter.py:150-170` |
| `latex.legacy_accents: bool` | `state.py:45` | `pylatexenc` path of `escape_latex_chars`; port the accent-brace fix `escaper.py:59-72` only |
| `headings.base_level: i8`, `headings.numbered: bool` | `writer.py:502`, `models.py:35,40` | absolute level = `Header.level + base_level - 1`; the slot offset is applied by the headings pass (§3) |
| `refs.textual_print/_web`; `numbering: BTreeMap<String, Backend \| Tmark>` | design 07 | `{page}` left to `\pageref`; figures/tables/equations `Backend` for LaTeX, declared counters `Tmark` |
| `typst.math: Mitex \| Native` | §4 | `Mitex` in phase 1.5 |
| `source_map: bool` | `--synctex-md` (new) | off → `map` empty |

Not options (runtime flags that become passes or contracts): `figure_template`
(`writer.py:1005`; the writer knows it is inside an admonition and emits
`\captionof`), `copy_assets`/`convert_assets`/`hash_assets` (`core.py:263-265`,
assets pass), `emoji_mode`/`emoji_command` (`core.py:489-496`, emoji pass),
`image_map` (`typst/writer.py:336`, assets pass), `callouts_definitions`/
`callout_style` (`writer.py:979`, `typst/writer.py:517`: kind validation moves
to `lint` against `ADMONITIONS` + `press.declare.admonitions`, Typst styling
becomes the `ts-callout` contract call), `drop_title` (`writer.py:487`: its
`\pagestyle{plain}` is the template wrapper's job).

### `Body`, `Requires`, `SourceMap` as Python sees them

`tmark.write(doc, "latex", options) -> dict`:

```python
{"text": str,
 "map": [[start, end, node_id], ...],            # byte offsets into text, block nodes + refs/images/captions
 "requires": {
   "packages": ["booktabs", "multirow", "longtable", "csquotes", "marginnote", "multicol", "ulem", ...],
   "fragments": ["ts-code", "ts-callouts", "ts-keystrokes", "ts-index", "ts-glossary", "ts-bibliography",
                 "ts-typesetting", "ts-fonts", "ts-equations"],   # ts-fonts only when a Span{script} was written
   "shell_escape": false,                          # minted block or \mintinline
   "assets": [{"src": "figs/a.pdf", "node": 12, "attrs": {"width": "50%"}}],
   "bibliography": true, "citations": ["knuth84", ...],   # ordered first-seen, replaces DocumentState.citations
   "acronyms": ["PWM", ...],                       # \acrshort keys emitted; ts-glossary declares only those
   "index": ["", "registry"],                      # "" = default registry; replaces has_index_entries/index_entries
   "counters": ["fw"]}}
```

Additions to design 07's struct: `citations`, `acronyms`. No longer from the
writer: `pygments_styles` (highlight pass), `script_usage`/`fallback_summary`
(scripts pass), `headings` (`context.py:97`, derive from the IR if a template
still reads it), `snippets` (`writer.py:734`, dropped), `callouts_used`
(`"ts-callouts" in fragments`), `requires_shell_escape` (`shell_escape`).
`tmark.write` runs once per slot document (§3) and Python unions the `Requires`.

## 2. LaTeX behaviours to port (from the Python writer)

**Escaping** (`writers/latex/escaper.py`, `writer.py`):
- Char map `escaper.py:23-34`: `^`→`\^{}` (0.6.x, c7e7d17), `~`→`\textasciitilde{}`, `\`→`\textbackslash{}`, `& % # $ _ { }` backslashed.
- Symbol map `escaper.py:36-49`: `→ ← ⇒ ⇐ ≥ ≤ ≠ ≈ ± × ÷ ∞` become `\(\rightarrow\)` etc. (math mode inside text).
- Order `escaper.py:301-313`: smart quotes → ASCII (`’`→`'`, `“`→` `` `, `”`→`''`, `…`→`...`, `:240`), dashes (`–`→`--`, `—`→`---`, `:232`), escape, then Unicode superscript/subscript runs → `\textsuperscript{…}`/`\textsubscript{…}` (`:124`, `:190`); the escaper skips those characters (`:89-96`) so the run pass sees them. Subscript Greek maps to `\beta` in text mode (`:223`): a latent bug, reproduce then fix in the allow-list.
- Math heuristic `escaper.py:253-262` + `writer.py:242-262`: `$…$`, `\(…\)`, `\[…\]`, `\begin{env}…\end{env}` inside a `Str` are passed verbatim. With tmark `$…$` is a `Math` node; `\(…\)` and environments typed in prose are not. Decision: the Rust writer does **not** scan `Str` for math; documents relying on it get a `lint` finding and the harness allow-lists them.
- `\keystroke{` guard `writer.py:251-254` (raw macro left verbatim): drop.
- Emoji segmentation `escaper.py:315-336`: becomes the emoji pass.
- URLs: `\href{requote_uri(url)}{text}` with the URL then run through `escape_latex_chars` (`formatter.py:142`), also for the figure `link` (`writer.py:1129`).

**Tables** (`writers/latex/tables.py`, `extensions/tables/layout.py`, `renderer.py`):
- Plain pipe table `tables.py:57-83` + `table.tex`: `\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}X…}` (`\raggedleft`/`\centering` per align), `\toprule`, header cells in `\textbf{}`, `\midrule`, `\bottomrule`; with caption `\begin{table}[H]\centering\caption{…}\label{…}\vspace{0.5em}` else `\begin{center}`. `_is_large` (`:91`) is dead code.
- Model table (`yaml`): env choice `layout.py:218-233` (`long`→`longtable`; explicit `X`/`auto` or a total width→`tabularx`; else `tabular`); column spec `layout.py:234-258`: fixed widths as `p{\dimexpr W-2\tabcolsep\relax}` (0.5.4), `%`→`\linewidth` fraction, align wrappers; header groups `renderer.py:43-60` with `\cmidrule(lr){a-b}`; `\multirow{n}{*}{}` / `\multicolumn{n}{align}{}` (`:116-123`), absorbed slots as empty `\multicolumn` (`:94`); labelled separators `\multicolumn{N}{l}{\textit{label}} \\` (`:175`), double rule `\midrule[\heavyrulewidth]` (`:166`); footer after `\midrule`; `longtable` emitted bare with `\caption{}\label{}\\`, `\endfirsthead`/`\endhead` (0.5.3, `yaml_table.tex`); placement `[htbp]` from `settings.placement`, else `[H]`.
- Cell content is written by `inlines()` with `in_cell` (a `CounterItem` in a cell starts with `\leavevmode`, 3bc9b10, `counter.tex`).

**Figures, captions, labels** (`writer.py:1018-1132`, `figure.tex`, `figure_tcolorbox.tex`):
- `\begin{figure}[H]\centering\includegraphics[width=…]{path}`; `width="50%"`→`0.5\linewidth`, absent→`\linewidth`; `\adjustbox{max width=\textwidth}` when the image is a generated diagram (`media.py:213`).
- `\caption[short]{long}\label{id}` — label **after** caption (0.5.0, 0.6.0); without caption a bare `\label`. Short caption = rendered `alt` unless longer than the caption (`writer.py:1112`, 0.6.0). `Figure.attrs.id` wins over `Image.attrs.id` (`:1045`). Inside an admonition: `\begin{center}…\captionof{figure}…\end{center}` (`figure_tcolorbox.tex`).
- A `Link` whose only content is an `Image` wraps the `\includegraphics` in `\href` (`:702`). `src#only-light|only-dark` stripped (`:1083`). A `Figure` wrapping a `Table` merges its caption into the table (`:1024-1039`).

**Footnotes, citations** (`writer.py:80-114`, `:838-877`): `\footnote{body}`; multi-line body → dropped with a warning (`:106`); a `Note` whose body is a comma-separated key list, or whose label is a bibliography key, becomes `\cite{k1,k2}` (`_ir_queries.py:36-58`) — under tmark this is `Ref` → `Resolution::Citation` and the shadowing rule of the audit; DOI keys (`doi.py:134`) are the doi pass.

**Lists** (`writer.py:553-576`, `:659-694`): `\item{} ` in `itemize` (note the `{}`), `\item ` in `enumerate`; task items → `\begin{todolist}` with `\item[\done]` (`choices.tex`); literal `[ ]`/`[x]` text prefixes also recognised (`:674`, drop: tmark has `ListItem.task`); a nested list environment is forced onto its own line (`:694`); definition list `\item[{ term }] body` (`description_list.tex`).

**Code** (`writer.py:355-373`, `:512-541`, `formatter.py:146-296`, `ts-code.jinja.sty:100-140`): block → `\begin{code}{lang}{title}{opts}` (the `tscode` contract: `baselinestretch=0.5` when the text contains box-drawing characters `:1237`, `linenos`, `highlightlines={1-3,7}` ranges), trailing newline guaranteed, `{`/`}` escaped under minted (`:518`), title escaped; inline: no lang or `inline_plain` → `\texttt{…}` with `\allowbreak{}` after each `inline_breaks` char; minted → `\mintinline[breaklines=true]{lang}|…|` with the first delimiter of `writer.py:37-49` absent from the text, sets `shell_escape`; pygments → produced by the highlight pass; listings/verbatim → `\texttt`.

**Math** (`writer.py:376-393`): inline `$…$` verbatim; display: an `align`/`equation` environment is emitted bare, anything else as `$$\n…\n$$` (`:1231`); `MathBlock.attrs.id` → `\label{}` inside the environment (new; legacy relied on `\label` typed in the math).

**Links** (`writer.py:696-747`): `http(s)` → `\href`; other schemes → error; `#id` → `\hyperref[id]{text}` or `\ref{id}` when no text (`ref.tex`); a `Ref` with a resolved label → `\hyperref[key]{Label}` for tmark-numbered series, `\ref` for backend-numbered; unresolved → `[?key]`; external inventory → plain text `RHE-423-FW-10 p. 14` (0.6.0). Local `.md` targets (`links.py:84-145`) are the links pass.

**Index** (`writer.py:890-922`, `extensions/index/renderer.py:15-60`, `index.tex`): `\index[registry]{sort@formatted!sub}`; `**b**`/`*i*` markup inside a tag formats the entry (`\textbf`), sort key is the stripped text and `sort@` is emitted only when it differs; `main=true` → `\textbf{…}` around the whole entry (style `b`); `Requires.index` collects registries.

**Glossary** (`writer.py:788-798`, `context.py:52-98`): `Abbr` → `\acrshort{key}`, key = `slugify(term, separator="", lowercase=False)` with `2`,`3` suffixes on collision; a term without description renders escaped text. The key algorithm must be identical in Rust (the `ts-glossary` fragment emits `\newacronym{key}`).

**Counters, cross-refs** (`counter.tex`, `label.tex`, 0.6.0): `CounterItem` → `\leavevmode\phantomsection\label{prefix:key}FW-01` with the number from `Resolved.counters.get(prefix).label(key)`; a silent `{#fw:x}` on a heading/figure stays the host's `\label`.

**Headings** (`writer.py:483-510`, `heading.tex`): level −1 `part`, 0 `chapter`, 1–3 `section…subsubsection`, 4–5 `paragraph`/`subparagraph` followed by `\mbox{}\\`, beyond → `\textbf{}`; `*` when not numbered; `\label{id}` after the title, id = `attrs.id` or `slugify(plain_text)` (python-slugify semantics: ASCII, `-`); newlines inside the title collapsed (`:495`); a paragraph that is a single `Strong` under 80 characters → `\tslead{…}` (`:454-481`, `lead.tex` also emits a `\providecommand` — moves to `ts-typesetting`).

**Media** (`writer.py:1063`): `copy_assets=False` renders the caption or `[image]` as text — the assets pass substitutes a `Str`. `HorizontalRule` → `\clearpage` (`horizontal_rule.tex`; spec: paged default). `Aside` → `\marginnote{…}`, `side=left` → `{\reversemarginpar\marginnote{…}}` (`:423-431`). `Keystroke` → `\keystroke{Ctrl} + \keystroke{S}` with the name table of `keystroke.tex` (arrows as `\(\uparrow\)`, unknown keys upper-cased). `Quoted` → `\enquote{}`. `Highlight` → `\texsmithHighlight{}` (the engine-conditional definition in `highlight.tex` moves to `ts-typesetting`). Critic spans: `\sout`, `\uline`, `\xout{a}\ \uline{b}` (`substitution.tex`). Block quote → `\begin{displayquote}\n\n…\n\end{displayquote}`; epigraph → `\epigraph{\itshape ``…''}{--- \textit{source}}`; multicolumn → `\begin{multicols}{n}`; `\LaTeX{}` logos from `TexLogo` are a `Str` pass (audit). Progress bar `_compose_latex` (`extensions/progressbar/renderer.py:19`) → `\tsprogressbar{fraction}{label}[thin]` contract.

**Zero-width** (spec §Attributes): `Comment`, `IndexEntry` with no visible text, `Aside`, a `Span` that is only an anchor (a `CounterItem` prints and is not zero-width). Rule in `common/zero.rs`: around a zero-width inline, trim trailing whitespace of the preceding `Str` when the following `Str` starts with whitespace or `.,;:!?)`, and trim leading whitespace of the following `Str` when the preceding one ended with whitespace. Legacy has no such rule; the harness shows single-space differences next to `{index}` and `{aside}`, allow-listed as spec behaviour.

**Script spans** (`writer.py:816-824`, `:974-990`): `Span{script=slug}` → `\text<slug>{escaped}`; block form (a `Div{script}` of paragraphs) → `\begin{<slug>}…\end{<slug>}`, consecutive siblings merged (`:146-173`). Under the pass of §3 only the inline form remains; the block form becomes a `Div{name=script}` container kept for `::: script` and rendered the same way.

## 3. Passes that stay in Python

Pure functions `(Document, ctx) -> (Document, diagnostics)` over the
generated models, under `texsmith/passes/`. Order and contracts:

| # | Pass | Reads | Writes | Why Python | Order |
| - | ---- | ----- | ------ | ---------- | ----- |
| 1 | `include` | `Block::Include{path, base}` | spliced blocks of the parsed file; `Image.src`, `CodeBlock.options.include`, nested `Include` rebased to the included dir; ids renumbered above the host max, spans keep their own `FileId` (`Attrs.relocate`, `tmark-ir/attrs.rs:74`); `Resolved.files` fed by the pass | file I/O (`--8<--` semantics are a splice; `\input` never) | first; before `resolve` so that one document is resolved and `Resolved.included` stays empty |
| 2 | `var` | `Inline::Var{path}` | `Str` from `(template_overrides, front_matter)` (`templates.py:78-104`; never inside code — the parser never makes a `Var` there) | needs the CLI contexts | before `resolve` (a var may sit in a heading that gets a label) |
| 3 | `headings` | `Header`, front matter `title` | title promotion: first `Header{level=1}` removed when `title` is absent (`typst.py:276`; `title: null` opts out); per-slot offset `1 - min(level)` (`core.py:307-316`) applied to `Header.level`; `press.base_level` left to `WriterOptions.headings.base_level` | template slot levels (`core.py:280`) | before `slots` |
| 4 | `snippet` / `exec` | `CodeBlock{lang=snippet}`; `Image{generate=…, code=…}` (opt-in) | `Figure{Image{src=<png/pdf>}, Caption}` or `Image` | nested build / subprocess | before `assets` |
| 5 | `doi` | `Ref` items whose key matches `10\.\d{4,9}/…` (`doi.py:23`), front-matter inline `bibliography:` entries (`templates.py:401`) | `RefItem.key` rewritten to the fetched entry key; a generated `inline-doi-<stem>.bib` (`doi.py:47`) appended to `ResolveOptions.bibliography`; DOI cache in the output dir (`templates.py:517`) | network | before `resolve` (the key must be in `Bib`) |
| 6 | `links` | `Link{Target::Document(path)}` (MkDocs-style `.md` links, `links.py:38-110` candidates) | `Link{Target::Anchor(first heading id of the target, via tmark.parse)}` or a diagnostic; the "snippet" fallback (`writer.py:734`) is dropped | file I/O | before `resolve` (anchor links are resolved there) |
| 7 | `assets` | `Image.src`, `Image.attrs` (`crop`, `width`), `Image{generate=mermaid}` | `.svg/.drawio/.mmd` → PDF (LaTeX) or PNG (Typst) via the converters (`assets.py:73-128`, `:217-226`, crop `:292`); remote URLs fetched with the manifest (`:130-215`); `%% caption` first line of a mermaid fence → `Caption` (`media.py:85`); `src` rewritten to the output-relative path or hashed name (`:352-380`); `copy_assets=False` → `Str` placeholder | processes, network, files | after `include`, `snippet`; independent of `resolve` |
| 8 | `emoji` | `Str` | clusters (`emoji.emoji_list`) → `Span{attrs: emoji=<cluster>}`; artifact mode → `Image{src=twemoji svg, width=1em}` (`writer.py:217-240`) | `emoji` library, fetch | before `scripts` (so an emoji is not classified as a script; legacy `scripts.py:346`) |
| 9 | `scripts` | `Str` (not inside `Code`, `Math`, `Raw`) | runs whose Unicode group is not in `{latin, common, punctuation, other}` (`scripts.py:26`) → `Span{attrs: script=<slug>}`; combining marks and diacritics join the current run (`:212-216`), whitespace joins when inside a run, CJK majority vote (`:235-262`), single Greek/Hebrew letter → `Math{\alpha}` (`:89-113`); output summary `script_usage` (slug, group, font, count) and `fallback_summary` for `ts-fonts` (`ts-fonts.jinja.sty:264-300`, `provisioning.py:485`) | Noto/ucharclasses metadata cache | after `var`, `emoji`; before `resolve` is fine (spans carry no id) |
| 10 | `resolve` | — | `Resolved` via `tmark.resolve(doc, loader, {path, bibliography, start})` | (Rust) | |
| 11 | `slots` | `Header` id/text selectors from `press.slot.*` (R5) | one `Document` per slot (block sub-slices keep their ids, so `Resolved.refs` stay valid); `*` = whole document | template binding | after `resolve`, before `write` |
| 12 | `highlight` | `CodeBlock`, `Code{lang}` when `code.engine == pygments` and backend is LaTeX | `Div{name=code, attrs: lang,title,linenos,hl_lines,baselinestretch, content=[RawBlock{latex, <Verbatim payload from Pygments LatexFormatter, verboptions "breaklines, breakanywhere, commandchars=\\\{\}", highlightlines>}]}`; inline → `RawInline{latex, "{\ttfamily …}"}` with `\allowbreak{}` between `\PY` macros (`pygments.py:141-161`); output `pygments_styles` for `ts-code` | Pygments | last before `write` |
| 13 | `write` | — | `tmark.write(slot_doc, backend, options)` per slot | (Rust) | |

Decision on scripts (R4): **a pass producing `Span{script=…}` before
`write`**, not a post-pass over the body text. The legacy wrapper ran on
rendered LaTeX and skipped any paragraph containing a backslash or math
(`writer.py:198-209`, `:637-639`), so a Cyrillic word next to an `\emph`
got no wrapper: the pass fixes that and the harness records it as an
intended difference. The whole-body fallback scan that drives
`ucharclasses` transitions (`renderer.py:359-386`) runs on `plain_text` of
the IR (one call, all slots) instead of the concatenated LaTeX.

`glossary`: tmark reads `press.declare.acronyms` and `*[X]: …` lines and emits
`Abbr` itself, so `append_synthetic_abbr_lines` (`glossary.py:213`) disappears;
verify on `examples/glossary` and `examples/abbr`, no pass unless it fails.

## 4. Typst math (R12)

Keep `mitex` in phase 1.5. The Rust `typst/math.rs` ports
`typst/writer.py:267-297`: `#mi(`…`)` inline, `#mitex(`…`)` display,
backtick fence longer than any run inside; `\label{k}` inside the text is
stripped and re-attached as ` <k>` after the call; a math node that is only
`\eqref{k}`/`\ref{k}` becomes `#ref(<k>)`; `MathBlock.attrs.id` becomes the
label (new, canonical). Every label goes through the same sanitiser as
bibliography keys (`[^A-Za-z0-9_.:-]` → `-`, `:932`, `typst.py:170`).
`Requires.packages += "@preview/mitex:0.2.6"`, `Requires.fragments +=
"ts-equations"` when a label was emitted (the template turns
`math.equation(numbering)` on). `baseline.md` records that `aligned` fails
inside mitex 0.2.6 on two examples: pre-existing, allow-listed. The
translator stays a post-M5 item behind `typst.math = native` with a
`math-untranslatable` diagnostic and a `raw` fallback; it is not on the
migration path because the PDF pixel diff would differ anyway.

## 5. Parity harness (`scripts/parity.py`, task 4.1)

**Corpus.** `docs/**/*.md` (93 pages, each rendered standalone with
`-tarticle`, plus the whole book through the MkDocs plugin as one entry once
3.9 lands) and every example. Entries come from a manifest
`tests/parity/corpus.yml`, derived once from the `examples/*/Makefile`
command lines (`texsmith X.md -oDIR -tarticle …`, `-M`, `-a…`, `--format
typst`) with `--build` removed: `{id, cwd, args, backend, requires:
[docker|network|fonts]}`. Examples needing Docker (mermaid, diagrams) are
skipped where the tool is missing and reported as skipped, never as passed.

**Runs.** `parity.py render --reader {html,tmark} --out build/parity/<reader>/`
renders each entry to `.tex`/`.typ` (no PDF). Until the Rust writer exists
only `html` exists; `parity.py baseline` renders with `html`, normalises,
and writes `tests/parity/baseline/<id>/<stem>.{tex,typ}` — **committed**,
so phase 0.1 (caption after the float) updates it in a reviewed diff and
phases 1–3 cannot drift the legacy output unnoticed. The `.bib`, DOI cache
and remote-asset manifest are seeded from `tests/parity/cache/` so runs are
offline and deterministic; the font metadata cache is seeded in CI.

**Normalisation** (both sides, before diffing): body extracted between
`\begin{document}` and `\end{document}` (or the slot `.tex` files) and
compared first; the full file is a second, non-gating diff. Rules: strip
lines that are `%` comments at column 0 and trailing `%…` outside verbatim
environments (`code`, `Verbatim`, `minted`, `lstlisting`, tracked by an
environment stack) — this also removes future line-marker comments; collapse
blank-line runs to one; strip trailing whitespace; one newline at EOF;
sha256 asset stems `[0-9a-f]{64}` → `<HASH>`; `.converted/` paths and
remote-asset names → basename; the document stem → `<STEM>`
(`inline-doi-<stem>.bib`, `main`); `\providecommand{\tslead}…` lines
dropped (moves to a fragment). `.typ`: strip `//` comment lines, collapse
blank lines, hash image names, strip the `#import "@preview/mitex…"` line.

**Allow-list** `tests/parity/allow.yml`, one entry per intended difference,
each with an owner reason and an expiry:

```yaml
- id: item-braces          # \item{} → \item
  kind: rewrite            # applied to both sides before diffing
  files: ["**/*.tex"]
  from: '\item{} '
  to: '\item '
  reason: "unordered_list.tex artefact; changelog 0.7.0"
  expires: 0.7.0
- id: zero-width-aside
  kind: hunk               # a diff hunk matching this regex is ignored
  files: ["docs/syntax/*.tex"]
  pattern: '^-(.*) \\marginnote\{(.*)\}\.$\n^\+\1\\marginnote\{\2\}\.$'
  reason: "spec §Attributes zero-width collapse"
  expires: 0.7.0
```

`parity.py diff` prints a per-entry table (identical / allow-listed /
differs, with the hunk count) and exits 1 on any unlisted difference.

**PDF.** `parity.py pdf --entries …` builds both sides with tectonic
(LaTeX) or `typst compile`, rasterises every page with pymupdf at 100 dpi
(`page.get_pixmap`), compares page counts, then the pixel difference after
a one-pixel dilation of both sides; fails when more than 0.1 % of a page
differs; writes an overlay PNG (legacy red, new green, like
`examples/multi-document/Makefile` `compare`) under `build/parity/pdf/`. A
text-layer diff (`page.get_text()`) runs first as a cheap classifier.

**CI.** `ci.yml` gains a `parity` job on every PR: `uv run python
scripts/parity.py baseline --check` (re-render legacy, diff against the
committed baseline; text only, seconds). Once `--reader tmark` exists the same
job runs `parity.py diff`; the phase 4 gate is "empty modulo allow-list". The
PDF diff runs nightly and on the `parity-pdf` label, on the Linux runner that
already builds the minimal examples.

## 6. Work items and open questions

tmark (ordered): (1) `Requires` gains `citations`, `acronyms`;
`WriterOptions` as §1; (2) `common/` with `Out`+`SourceMap`, zero-width,
media, refs; `latex/escape.rs` with the `escaper.py` tables and the
escaper tests ported as unit tests; (3) HTML writer; (4) LaTeX writer in
the order the harness bites: para/inline, headings, lists, code (`tscode`),
plain tables, model tables, figures/captions, footnotes/citations, index,
glossary, counters, asides, admonitions, keystrokes, math; (5) Typst writer
with `math.rs` (mitex); (6) `FRAGMENTS` table (`ts-code`, `ts-callouts`,
`ts-keystrokes`, `ts-index`, `ts-glossary`, `ts-bibliography`,
`ts-typesetting` = `\tslead`, `\tsdiv`, `\texsmithHighlight`,
`\tsprogressbar`, epigraph; `ts-fonts`, `ts-equations`); (7) `tmark write
--map`; (8) `Div{name=code}` accepted by the LaTeX writer as the highlight
contract; (9) table validation diagnostics (R6).

TeXSmith (ordered): (1) `scripts/parity.py baseline` + `corpus.yml` +
committed baseline, CI job — before any Rust line; (2) phase 0.1 and the
baseline update; (3) passes of §3 with IR-fixture tests, in the order
`include`, `var`, `headings`, `assets`, `doi`, `links`, `emoji`, `scripts`,
`highlight`, `snippet`; (4) `Requires` → fragment activation
(`wrapper.py:121-194` rewritten), `pygments_styles` and `script_usage` from
the passes; (5) `--reader tmark` end to end on `examples/markdown`, then the
corpus; (6) allow-list triage, changelog.

Open questions: (a) `HorizontalRule`: emit `\clearpage` directly (byte
parity) or `\tsdivider` (restylable) — proposal: `\clearpage` now, macro at
0.8; (b) heading ids without `{#id}`: python-slugify vs Python-Markdown
`toc` slugs differ on accents; the writer must pick one and the docs'
`[text](#slug)` links follow — decide before 1.4; (c) does the parser emit
`Abbr` for `press.declare.acronyms` and `*[X]:` alike, and which wins on a
duplicate key; (d) `Note` with a multi-line body: keep dropping with a
warning, or render `\footnote{}` with `\par` — spec says "one line in
print", so a `note-multiline` diagnostic and a drop; (e) `Div{name=script}`
for `::: script`: keep, or lower to spans in the pass and delete the block
form; (f) `Requires.assets` once the assets pass rewrites `src` before
writing: keep it as the copy list; the pass owns conversion.
