# Python IR, `Document` and the pass framework

Status: design note for `specs/tmark-migration.md` D2, D6, D7, R3, R5, R11 and the framework half
of phase 3.3 (pass contents are designed elsewhere). Paths as of `tmark-migration` and tmark `main`.

## 1. Generated models (`texsmith/ir/model.py`)

**Tool choice: a small custom generator (~350 lines), not `datamodel-code-generator`.** Three
facts of `crates/tmark-ir/schema/ir.json` decide it. `Block` and `Inline` are `oneOf` lists of
*anonymous* variants (no `title`, no `discriminator`; the tag is `properties.type.enum[0]`), so
`datamodel-code-generator` names them `Block1`…`Block19`, `Inline1`…`Inline28` and emits an
undiscriminated `Union` that pydantic validates by trial — slow, with useless errors. `Meta` is
flattened (`id`, `span` as sibling keys, defaults skipped) and Rust equality ignores both
(rule 3); pydantic `frozen=True` compares every field, dataclasses give `field(compare=False)`.
And today's `texsmith.ir` is frozen, slotted dataclasses with `tuple` children discovered by
`dataclasses.fields`: generating the same kind of class keeps `walk`/`children`/`map_tree`, the
IR tests and every reader construction site unchanged. Validation cost: the producer is the pinned
wheel, so the decoder trusts the shape and checks only the tag and required keys (`IRDecodeError`
names the path); pure-Python decoding of a documentation page (≤ 10 k nodes) is under 100 ms, and
if a profile disagrees the fix is msgpack on the Rust side (`09-bindings.md`), not pydantic.

```python
@dataclass(frozen=True, slots=True)
class Para(Block):
    type: ClassVar[Literal["Para"]] = "Para"
    content: tuple[Inline, ...] = ()
    lead: tuple[Inline, ...] | None = None
    id: int = field(default=0, compare=False)          # Meta, flattened
    span: Span = field(default=NO_SPAN, compare=False)
```

Per schema definition the generator emits: `Node`/`Block`/`Inline` bases and `Block = Para |
Plain | …` aliases for pyright; `Row` and `Target` as tagged unions; enums as `enum.Enum` with the
`snake_case` values; `Span(file, start, end)`/`SubSpan` decoded from `[f, s, e]`, `NO_SPAN =
Span(0, 0, 0)`; the front-matter types (`FrontMatter`, `Keys`, `Press`, …; JSON-typed fields stay
`Any`; `Keys.title` is `str | None | Missing` so `title: null` survives); `TableModel`;
`decode_document`/`encode_document` (defaults skipped, `encode(decode(x)) == x` for tmark output)
with dispatch tables keyed on the tag; `structural(doc)`, the twin of Rust `structural_json`.

Script and drift check: `scripts/gen_ir_models.py` reads `tmark.schema("ir")` from the *installed*
wheel, writes `model.py` under a header naming the tmark version and schema hash, and exits 1
under `--check` when the committed file differs (CI, lint job). `texsmith.ir` compares the
generated `SCHEMA_HASH` with `tmark.schema_hash()` at import and raises `ImportError` naming both
versions; `decode_document` checks the root `"tmark"` field (phase 2.4) for a major match. Pin
`tmark>=0.X,<0.X+1`; every bump regenerates.

Names during the transition: `model.py` lands beside `nodes.py`; `texsmith.ir` re-exports `nodes`
until 3.8, then `model`; `nodes` is then imported only by the two Python writers until phase 5.
After the switch `MarginNote = Aside` and `MarginSide = Side` (`OUTER`/`INNER` added) are kept as
aliases; `Cite` gets **no** alias (`Cite(keys)` and `Ref(items, bracketed)` differ in shape and its
three consumers are rewritten anyway); `TexLogo`, `ProgressBar`, `Header.numbered/identifier`
disappear (`Str` pass, M5, `attrs.id`); `ir.Document.content` becomes `blocks`. `NodeVisitor`,
`walk`, `children`, `map_tree`, `plain_text` keep their signatures in `texsmith/ir/walk.py`.

## 2. The `Document` model (`core/documents.py`)

```python
@dataclass(slots=True)
class Document:
    source_path: Path
    kind: InputKind                 # MARKDOWN (tmark reader) | HTML (HtmlReader)
    ir: ir.Document                 # ir.file == 0
    files: FileTable                # FileId -> SourceFile(path, text, line_index)
    keys: ir.Keys                   # typed front matter (ir.front_matter.keys)
    press: dict[str, Any]           # TeXSmith's validated view (normalise_press_metadata)
    diagnostics: list[Diagnostic]   # parse, passes, resolve, write; deduplicated
    slots: SlotPlan                 # selectors, includes, options, requests
    base_level: int = 0; title_strategy: TitleStrategy = TitleStrategy.KEEP
    numbered: bool = True; suppress_title_metadata: bool = False
    extracted_title: str | None = None; language: str | None = None   # set by prepare
    bibliography: dict[str, Any] = field(default_factory=dict)
```

- `_html` is gone. `front_matter` stays as a *property* returning the legacy mapping (typed keys
  re-serialised at the root and under `press`, merged with `extra`), so `build_template_overrides`
  and the mustache contexts do not change; `set_front_matter` rebuilds `keys`/`press` from a
  mapping; `persist_debug_artifacts` writes `<stem>.ir.json`.
- `FileTable`: `add(path, text) -> FileId`, `path(id)`, `text(id)`, `line_index(id)` (lazy). Id 0
  is the source; the include pass and the loader add the rest; HTML input has `text=""`, `NO_SPAN`.
- `from_markdown(path, *, reader="tmark" | "html", …)` reads the text, expands front-matter
  mustaches (section 5), calls `texsmith.readers.tmark.read(text, file_id=0, name=str(path))`
  (`tmark.parse` → `decode_document`), seeds `diagnostics` from the parse result, then
  `_initialise_slots_from_front_matter` as today. `from_html` keeps its selector logic and calls
  `HtmlReader(...).read(fragment)`. The reader (`readers/html/reader.py`) is retargeted to build
  `texsmith.ir.model` nodes: dense ids from its own counter, `NO_SPAN` everywhere,
  `Header.identifier` → `attrs.id`, `MarginNote` → `Aside`, `Cite(keys)` →
  `Ref(items=[RefItem(key=k)])`, whitespace kept inside `Str` (no `Space`: the parser never emits
  it, the Rust writers must not depend on it). After 3.8 both readers feed the same pipeline.
- `prepare_for_conversion` keeps its contract but reads the IR: `first_heading_level()` and
  `_extract_promoted_title` walk top-level `Header` nodes with `plain_text`; `heading_analysis.py`
  goes with the HTML path. Passes run after it. `copy()` shares `ir` and `files`, copies the rest.

## 3. The pass framework (`texsmith/passes/`)

```python
Pass = Callable[[Document, PassContext], Document]

@dataclass(slots=True)
class PassSpec:
    name: str; run: Pass
    after: tuple[str, ...] = ()   # ordering constraints, checked at registration
    needs_io: bool = False        # pure passes are tested without a filesystem

@dataclass(slots=True)
class PassContext:
    files: FileTable              # shared with Document; include registers files here
    ids: IdAllocator              # next(), reserve(n); floor above max(id) of every file
    diagnostics: DiagnosticSink   # emit(...); dedup on (code, span, message)
    loader: Loader; output_dir: Path; request: ConversionRequest   # request is read-only
    contexts: tuple[Mapping, ...]; emitter: DiagnosticEmitter      # mustache contexts; events only
```

Ordering: `DEFAULT_PIPELINE` is the explicit list `include, var, snippet, assets, doi, scripts,
glossary` (`highlight`, `exec` later), then `resolve` (Rust, once, on the whole document), then
`slots` and `headings` (block sub-slices keep their ids, so `Resolved` stays valid per body);
template and plugin passes register a `PassSpec` with `after=`, and `build_pipeline()` does a
stable topological sort, raising at startup on a cycle. A pass never mutates its input.

Ids and files: node ids are unique per file but not dense (`~/tmark/design/13-handoff.md`); the
only invariant TeXSmith relies on is "every id of every file is below `ids.floor`", maintained by
`IdAllocator.observe(ir)` after each parse. The include pass parses with `tmark.parse(text,
file_id=ctx.files.add(path, text))`, re-keys the included ids by an offset from
`ids.reserve(count)` (spans already carry the new `FileId`), splices `blocks`, merges `footnotes`
and `abbreviations`, recurses depth-first with a cycle guard, and rebases relative `Image.src`,
`CodeBlock include=` and nested includes to the main document's directory (`Include.base`
honoured). A missing file becomes `Para([Str("[include: x.md not found]")])` plus
`include-missing` at the `Include` span, so `tmark.resolve` sees no `Include` to report twice.

Spans, three rules checked by a test helper `assert_spans_preserved`: (1) a rewritten node keeps
`id` and `span` (`replace`); (2) a node derived from another (`Var` → `Str`, `CodeBlock` →
`Image`, `Str` run → `Span{script}`) takes the source's `span` and a fresh id; (3) a node created
from nothing (`Abbr` from front-matter acronyms) takes its cause's span (`ir.front_matter.span`)
or `NO_SPAN`. Included spans need no mapping: they carry their own `FileId`. Rules 1–2 keep the
source map alive.

Diagnostics from a pass: `ctx.diagnostics.emit(code, span, message, *, severity=None, fix=None,
related=())`, severity defaulting from the code table (section 6). Failures never raise: the node
is replaced by a visible literal (`Str("[asset: fig.drawio: conversion failed]")`, the `Ref` left
for `[?key]` rendering, the `CodeBlock` kept as code) and a diagnostic is emitted at its span.
Exceptions escaping a pass are bugs and propagate. `--strict` is evaluated after the pipeline.

Tests: `tests/passes/<pass>/<case>.md` is the authored input; `make ir-fixtures` runs `tmark parse`
into the committed `<case>.in.json`; `<case>.out.json` is the expected `structural()` result,
`<case>.diag.json` the expected `(code, span, message)` list; `run_pass(name, fixture,
loader=MemoryLoader({...}))` builds a `PassContext` over an in-memory `FileTable`. No HTML.

## 4. Slots on the IR (`passes/slots.py`, replaces `extract_slot_fragments`)

Selector grammar kept from `parse_slot_mapping`: `#id` (matches `Header.attrs.id`), bare text
(matches `plain_text(Header.content)`, trimmed), wildcards `@document` / `*`, the string form
`"name:selector"` (also the CLI `--slot name:selector`); mapping and list shapes unchanged.
Anything else (`.class`, `div > h2`, attribute selectors) emits `slot-selector-unsupported`
(warning, front-matter span) and the content stays in the default slot. Only **top-level** headers
are candidates; a match inside a container emits `slot-nested-heading`.

Algorithm over `ir.blocks`, mirroring the bs4 version: (1) wildcard slots take the whole block
list; if any exists the default slot receives nothing. (2) For each requested slot in request
order, find the first unclaimed top-level `Header` by id, then by text; none → `slot-missing`.
(3) A section is the header plus the following top-level blocks up to the next `Header` with
`level <= header.level`; claimed sections are removed, the remainder is the default slot.
(4) `strip_heading` (template manifest) or `flatten` (front matter) drop the header. (5) Each
`SlotBody(name, blocks, position, heading_levels)` records heading levels in order, descending
into `Div`/`Admonition` as `_heading_levels_for_nodes` did.

`headings` pass, per body: `offset = 1 - min(heading_levels)` (0 when empty; the first level is
skipped when `drop_title` applies to the default slot), `base_level = slot_levels[name] +
document.base_level + offset`, passed as `WriterOptions.headings.base_level` of the `tmark.write`
call for that body rather than written into `Header.level`, so the IR stays the author's. Title
promotion under `PROMOTE_METADATA`: when the first top-level block is a `Header` at level L and L
occurs once, `plain_text` becomes `extracted_title` and the header is dropped (`drop_title`);
`keys.title is MISSING` allows it, `None` (`title: null`) opts out. Front matter `numbered` and the
`preface` rule set `WriterOptions.headings.numbered=False` per body. Each writer call receives
`replace(ir, blocks=body.blocks)` with the full `footnotes`/`abbreviations`. For users: CSS
selectors and headings nested in `<div markdown>` stop working (warned); nothing else changes.

## 5. Front matter and moustaches

Split: tmark parses the YAML, types `title, subtitle, authors, date, id, lang, epigraph,
press.{base_level, declare, sources, features}`, applies "press wins" per key, moves the deprecated
root spellings (`bibliography`, `counters`, …) into their group and lists them in
`front_matter.deprecated`. TeXSmith rebuilds the legacy mapping (section 2) and runs
`normalise_press_metadata` on it unchanged (authors, `press.`/`press/` keys, nested aliases).
Its own deprecated spellings — `entrypoints` (→ `slots`), `author` (→ `authors`), `press.x` dotted
root keys, `press/x` — join tmark's list as `deprecated-frontmatter-key` diagnostics whose message
names the replacement; no automatic fix, since front-matter keys are not node spans and `tmark
lint --fix` does not rewrite them either. The `warnings.warn` of `_coerce_common_strings` becomes
`frontmatter-root-overrides-press` (info). `PressMetadataError` and
`InlineBibliographyValidationError` keep raising `ConversionError` (invalid metadata has no
sensible literal) and are also recorded as errors at `ir.front_matter.span`.

Moustaches, in order: (a) `replace_mustaches_in_structure` over the template overrides and the
front-matter mapping runs in `resolve_conversion_context` as today, before any pass (unresolved →
`var-unresolved` at the front-matter span). (b) The `var` pass
substitutes body `Var{path}` nodes by dotted lookup in `ctx.contexts` (overrides, front matter,
`_build_mustache_defaults`): a scalar becomes `Str(str(value))` (span rule 2); a list or mapping
emits `var-not-scalar`; a missing path leaves the `Var`, emits `var-unresolved` at its span, and
the writers print the moustache verbatim (today's behaviour). No skip-tag logic: the parser never
forms `Var` inside code, math or raw. `_replace_mustaches_in_html` goes with the HTML path.

## 6. Diagnostics

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:                   # texsmith/diagnostics/model.py
    code: str                       # kebab-case: tmark's ids or TeXSmith's
    severity: Severity              # hint | info | warning | error
    span: Span                      # NO_SPAN when there is no location
    message: str                    # one sentence, no trailing period
    fix: Fix | None = None          # (span, replacement)
    related: tuple[tuple[Span, str], ...] = ()
    origin: str = "texsmith"        # "tmark" for parse/resolve/lint/write records
```

It is the JSON of `tmark_ir::Diagnostic` plus `origin`, `code` as `str` (Rust's `Code` is a closed
enum). TeXSmith's codes and default severities live in `texsmith/diagnostics/codes.py`:
`include-missing`, `deprecated-frontmatter-key` reuse tmark's ids; new are `asset-missing`,
`asset-convert-failed`, `doi-fetch-failed`, `snippet-build-failed`, `slot-missing`,
`slot-selector-unsupported`, `slot-nested-heading`, `var-unresolved`, `var-not-scalar`,
`font-missing`, `frontmatter-root-overrides-press`, `file-unreadable` (none shadows a tmark id, T2).

Rendering: `format_diagnostic(d, files)` prints `{path}:{line}:{col}: {severity} {code}: {message}`
with **1-based line and 1-based byte column**, computed on the Python side by
`FileTable.line_index(d.span.file).line_col(d.span.start)` (a bisect over the line starts of
`text.encode()`): TeXSmith owns every file text and passes emit after the Rust side returned, so
Python is the one place that can render every record. The convention is `tmark-cli`'s
(`at.line + 1`, `at.col + 1`), so both tools print identical lines for identical findings (parity
test). `NO_SPAN`, or a file without text (HTML input), renders as `{path}: {severity} {code}:
{message}`; `fix` and `related` print indented at verbosity ≥ 1.

`--strict` (CLI) and `press.features.strict` make any `warning` or `error` fail the run with exit
1 after the bodies are written and before the engine runs, so the `.tex` is there to inspect;
`PYTHONWARNINGS=error` leaves the docs. `warnings.warn`/`warn_author` leave `core/` and
`writers/`: the crossrefs resolver goes to tmark, the inventory writer's staleness messages get
the `press.sources.crossrefs` span, `metadata.py`, `fonts`, `git_version`, `document_date` and
`templates/manifest` emit through the sink with `NO_SPAN`. `DiagnosticEmitter`
keeps `event()`, gains `diagnostic(d)`; `warning()`/`error()` become wrappers building
`Diagnostic(code="texsmith", span=NO_SPAN)` so engine and network messages share the collector.
`CliEmitter.diagnostic` renders through `format_diagnostic` (Rich colour by severity, plain when
not a TTY); the summary ends with `N errors, M warnings` grouped per file and sorted by `(file,
span.start)`; `-q` hides hint/info; `--diagnostics-json PATH` dumps the list for editors and CI.

## 7. `Loader` and `ResolveOptions` on the Python side

```python
class TexsmithLoader:                                   # satisfies tmark's Loader protocol
    def load(self, from_path: str, rel: str) -> str | None:
        target = join(from_path, rel)                   # same rule as tmark_registry::loader::join
        try: text = Path(target).read_text(encoding="utf-8")
        except FileNotFoundError: return None           # tmark reports include-missing etc.
        except (OSError, UnicodeDecodeError) as exc:
            self.sink.emit("file-unreadable", NO_SPAN, f"'{target}': {exc}"); return None
        self.files.add(Path(target), text); return text # diagnostics in that file render by name
```

`join`: absolute `rel` as is; otherwise `dirname(from)` (or `from` itself when it has no
extension) joined and normalised textually, no symlink resolution — identical to tmark so the LSP
and TeXSmith agree on a path, and to today's rules (snippets from the document's directory,
inventories from `document_dir / inventory`, the MkDocs companion passing `abs_src_path` as
`from`). Not through the loader: DOI, images, executed fences (passes). `MemoryLoader` for tests.

`ResolveOptions` built by `core/conversion/resolution.py` (phase 3.4): `path` =
`document.source_path.resolve()`; `bibliography` = CLI `.bib` files made absolute against the cwd,
deduplicated in CLI order (front-matter `press.sources.bibliography` entries stay in the document
and are read through the loader); `start` = per prefix, the next value after the previous document
of the batch (`ConversionService.execute` chains in input order, MkDocs in nav order), replacing
the shared global `CounterRegistry`. The `doi` pass runs before resolve so pending DOI entries are
materialised when tmark loads sources. `resolve` runs once per document on the full IR; the
per-slot `write` calls receive the same `Resolved` (T1), so numbering does not restart per slot.

## 8. Work items and open questions

tmark, ordered: **T1** `tmark-py`: `parse(text, file_id=0, name="<memory>")`; `resolve(doc,
loader, options) -> dict` with `schema("resolved")` (counters with `next` per prefix, labels,
refs, pending DOIs, files, diagnostics); `write(doc, backend, options, loader, resolved=...)`.
**T2** IR root `"tmark"` field, `tmark.schema_hash()`, `schema("diagnostic")`, `tmark.codes()`.
**T3** Make node ids dense or amend `03-ir.md` §Identity to "unique per file" (all TeXSmith
assumes). **T4** Optional `#[schemars(title)]` on variants. **T5** Document the column convention
in `05-diagnostics.md`. **T6** `WriterOptions.headings { base_level, numbered }` in the writers.

TeXSmith, ordered (phase 3): **S1** `scripts/gen_ir_models.py`, `ir/model.py`, `ir/walk.py`,
`ir/codec.py`, CI `--check`, `tests/test_ir_*` ported (3.1). **S2** `diagnostics/model.py`,
`codes.py`, `DiagnosticSink`, `FileTable`, `format_diagnostic`, `CliEmitter.diagnostic`,
`--strict`, `--diagnostics-json` (D7; everything after needs it). **S3** `readers/tmark.py`,
`readers/loader.py`, the `Document` of section 2, `prepare_for_conversion` on the IR, `--reader`
(3.2). **S4** `passes/__init__.py` (`PassSpec`, `PassContext`, `IdAllocator`, `build_pipeline`,
`run_pipeline`), the `tests/passes/` harness, then `include`, `var`, `slots`, `headings` (3.3).
**S5** `core/conversion/resolution.py` (`ResolveOptions`, chained `start`), inventory writer
moved, `warn_author` removed (3.4). **S6** HtmlReader retargeted, `Space` dropped,
`heading_analysis.py` and `_replace_mustaches_in_html` deleted (3.8).

Open questions: (1) per-heading unnumbered marker — the spec has no `{-}`/`.unnumbered`; spec
challenge, or `WriterOptions.headings.numbered` per body only? (2) Byte versus character column:
both sides print bytes, editors expect characters; change both or neither. (3) Slot
selectors matching headers nested in `Div`/`Admonition` (bs4 did; section 4 says no) — decide from
the corpus before the flip. (4) `title: null`: `normalise_press_metadata` treats `None` as absent;
keep `MISSING` on `keys` only, or teach the press view too. (5) `Var` resolving to a list
(`authors`): today stringified, `var-not-scalar` is stricter; keep the warning or join with `, `?
(6) `writers-and-passes.md` runs `headings` before `slots` and writes the offset into
`Header.level`; this note keeps `Header.level` and passes a writer option. Settle before S4.
