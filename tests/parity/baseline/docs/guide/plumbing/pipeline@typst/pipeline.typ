#set document(
title: "How does TeXSmith work?",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[How does TeXSmith work?]]
#v(1.5em)

#ts-callout-style.update("fancy")

TeXSmith ingests *Markdown* (`.md`), *YAML* (`.yaml`) and *#ts-logo("BibTeX")*
(`.bib`), then runs them through a conversion pipeline to produce #ts-logo("LaTeX"), Typst,
or a finished PDF.

Templates define the layout and expose slots that get filled with content from
your sources. The template also relies on *fragments* — extra layers that add
a bibliography, glossary, fonts, page geometry, or other typesetting options.

#figure(
image("workflow.pdf"),
caption: [Workflow diagram of TeXSmith],
)

= The shape of the pipeline

```
.md ──tmark.parse──▶ IR ──TeXSmith passes──▶ IR' ──tmark.resolve(loader)──▶ Resolved
                     pre:  include · glossary · var · title · snippet ·
                           assets · doi · emoji · scripts
                     post: slots · headings · highlight
                                                                          │
      ┌───────────────────────────────────────────────────────────────────┘
      ▼
  tmark.write(IR', "latex" | "typst" | "html") ──▶ Body { text, map, requires }
      │
      └─▶ Requires → fragments → preamble; text → template slots; engines → PDF
```

Two rules keep the boundary honest. A function that needs a file, a clock, a
process or a socket is *TeXSmith's* (or hides behind a `Loader`). A writer
that needs to know the template, the font, the packages or the geometry is
asking for a *fragment contract*, not an option.

What lives where:

#table(
columns: 2,
align: (left, left),
table.header([Concern], [Owner]),
[Parsing, the IR, resolution, the canonical printer, the linter], [tmark (Rust)],
[The #ts-logo("LaTeX") / Typst / HTML writers], [tmark (Rust)],
[Templates, fragments, fonts, engines], [TeXSmith],
[Includes, executed fences, diagram conversion, asset hashing], [TeXSmith passes],
[Bibliography output (pybtex, DOI fetch, CSL)], [TeXSmith],
[Cross-document inventory writing], [TeXSmith],
[The CLI and the MkDocs companion], [TeXSmith],
)

= Internal pipeline

+ *Collect and classify inputs.*
The CLI and `ConversionService` accept Markdown documents, optional
front matter YAML, and bibliography files. `split_inputs` peels off
`.bib`\/`.bibtex`, treats a lone YAML file as the only document when needed,
and normalises any provided front matter. When documents share front matter,
it is deep-merged into each `Document`, with `press.*` metadata validated up
front to avoid surprises later.
+ *Parse to the IR.*
`tmark.parse` reads the source and produces the intermediate representation:
a typed tree with a committed JSON schema, plus the front matter and a source
span for every node. `texsmith.ir.model` is the generated Python mirror of
that schema, so the Python side never hand-writes the node catalogue. Parse
diagnostics — including the deprecation warnings of
Migrating to TMark — land in the render's
`DiagnosticSink`.
+ *Run the `pre` passes.*
A pass is a pure function `(Document, PassContext) -> Document` over the
generated models: it never mutates its input, returns the same object when it
has nothing to do, and never raises — a failure becomes a visible literal in
the output plus a diagnostic at the node's span. Most `pre` passes need I/O,
which is exactly why they are Python's. In their declared order:
#table(
columns: 3,
align: (left, left, left),
table.header([Pass], [I/O], [What it does]),
[`include`], [yes], [splices `{include}(file)` and fence `include=` sources, rebasing relative paths],
[`glossary`], [], [validates the structured `press.declare.glossary` section and declares one abbreviation per entry, so the prose substitutes the key and the backmatter lists it],
[`var`], [], [expands `{{ key }}` moustaches against the front matter],
[`title`], [], [promotes the first heading to the document title],
[`snippet`], [yes], [renders `.snippet` fences into preview figures],
[`assets`], [yes], [converts and hashes images and diagrams (mermaid, draw.io, SVG)],
[`doi`], [yes], [fetches pending DOIs into a generated `.bib`],
[`emoji`], [yes], [picks the emoji rendering mode and its assets],
[`scripts`], [yes], [detects non-Latin runs and chooses fallback font families],
)
Order is declared, not implicit: each pass registers a `PassSpec` with
`after=`, and `build_pipeline` performs a stable topological sort that raises
`PassOrderError` on a cycle — so the table reads as a listing, not as a
contract, and the constraints are what actually hold (`assets` after
`include` and `snippet`, `emoji` after `assets`, `scripts` after `var` and
`emoji`). A template or plugin registers its own the same way, and a `pre`
pass declared `after` a `post` pass is refused. `DEFAULT_PIPELINE` in
`texsmith.passes` is the list the CLI runs.
+ *Bind the template and attributes.*
`bind_template` resolves which template runtime to use and which slots exist.
Template attributes declared in `manifest.toml` are merged in a strict order:
template defaults #ts-script("symbols")[→ ]fragment defaults #ts-script("symbols")[→ ]front matter (`press.*`) #ts-script("symbols")[→]
CLI/session overrides. Attribute ownership is enforced so two fragments (or
the template) cannot claim the same attribute.
+ *Resolve once.*
`tmark.resolve` walks the whole document with a `Loader` supplied by
TeXSmith and turns every anchor, reference, citation and counter item into a
resolved label: "Figure 3", "FW-01", a citation key, a glossary entry, a
cross-document inventory hit. Resolution happens *once*, over the whole
document, so numbering is consistent across slots and unresolved references
are reported with their span instead of silently disappearing.
+ *Run the `post` passes.*
These only slice the block list or compute per-body options, so the
`Resolved` of the whole document stays valid: `slots` splits the tree into
the template's slots, `headings` computes the per-slot heading offset, and
`highlight` renders Pygments payloads for the #ts-logo("LaTeX") backend.
+ *Write one body per slot.*
`tmark.write(ir, backend)` emits the body text for `latex`, `typst` or
`html`, together with a *source map* (for SyncTeX) and a `Requires`
record. `Requires` is the writer's demand on the template, and it is what
makes the boundary work: the packages the body needs, the `ts-*` fragments
that must provide its contract macros, whether shell escape is required, the
assets to copy, whether a bibliography exists, and the cited keys, acronyms,
index registries and counter series actually used.
+ *Activate fragments from `Requires`.*
The unioned `Requires` of every slot drives fragment activation: a body that
emits `\tscallout` pulls in `ts-callouts`, one that emits `\tsindex` pulls in
`ts-index`, and so on. A macro the writer names, a fragment must define — the
check is by construction rather than by sniffing the rendered #ts-logo("LaTeX"). See
Contract macros.
+ *Fonts, bibliography and index.*
The script usage collected by the `scripts` pass chooses per-script font
families and emits font-switching commands; `–fonts-info` surfaces the
detected scripts and counts. Only the cited keys are written to the
generated `texsmith-bibliography.bib`, keeping outputs lean. The index
registries listed in `Requires` decide which `\printindex` blocks the
`ts-index` fragment drops into the backmatter.
+ *Template wrap and emission.*
Slot bodies are merged back into the template entrypoint by
`wrap_template_document`, alongside template/fragment attributes, required
assets, and optional manifest/debug artefacts. The resulting
`TemplateRenderResult` carries the main `.tex` (or `.typ`) path, per-fragment
outputs, the bibliography path, the selected engine and its shell-escape
requirement, ready for Tectonic, latexmk or the Typst compiler to produce the
final PDF. Each conversion also publishes its `.refs.json`
inventory for other documents to cite.

= Inspecting a stage

```bash
tmark parse report.md            # the IR as JSON, diagnostics on stderr
tmark check --strict report.md   # parse, resolve and lint
tmark write --to latex report.md # the body a slot receives (--map for Requires)
texsmith report.md --debug       # keep the intermediate artefacts
```
