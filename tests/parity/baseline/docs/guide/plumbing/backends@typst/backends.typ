#set document(
title: "Output backends",
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
#text(size: 1.8em, weight: "bold")[Output backends]]
#v(1.5em)

TeXSmith lowers every document into a typed intermediate representation (IR)
and then emits a backend from that IR:

```
read(HTML) → IR (texsmith.ir) → write(IR) → LaTeX | Typst
```

Because both backends consume the *same* IR (the readers and the IR are
untouched), you choose the output format with a single flag:

```bash
texsmith doc.md -tarticle --format latex   # default
texsmith doc.md -tarticle --format typst
```

`–format` is case-insensitive and accepts `latex` (default) or `typst`.

= #ts-logo("LaTeX") backend (default)

The #ts-logo("LaTeX") backend (`texsmith.writers.latex`) is the full-featured path: it
drives the template/fragment runtime, fonts and script matching, glossary and
index engines, asset transformers, and compiles through a #ts-logo("TeX") engine
(Tectonic by default, or `latexmk` with `–engine lualatex` / `–engine
xelatex`). This is the backend assumed throughout most of this documentation.

= Typst backend

#ts-callout(kind: "warning", title: [Experimental])[
The Typst backend is *experimental*. The #ts-logo("LaTeX") backend remains the
default and the supported path; Typst covers a subset of it, leans on the
third-party `mitex` package for math (which can fail on some constructs —
see below), and approximates or drops a few constructs. Use it for new,
Typst-first documents and check the output; do not assume #ts-logo("LaTeX")-level
fidelity yet.]

#link("https://typst.app")[Typst] is a modern, Rust-based typesetting system. The
Typst backend (`texsmith.writers.typst`) emits a compilable `.typ` source from
the same IR. It is a lean, Typst-native path and intentionally covers a
*subset* of the #ts-logo("LaTeX") backend (see #link(<scope-and-limitations>)[Scope]).

```bash
# Emit a .typ file (no compiler required)
texsmith doc.md -tarticle --format typst --output build/

# Emit and compile to PDF
texsmith doc.md -tarticle --format typst --build --output build/
```

Without a template, the body is wrapped in a minimal standalone preamble. With
the *article* or *book* template, the body is wrapped in the template's
Typst scaffolding (title, authors, date, abstract, table of contents,
sectioning, and a native Typst bibliography).

#ts-callout(kind: "note", title: [Typst output and #ts-logo("LaTeX")-only flags])[
`–format typst` cannot be combined with `–html`, `–template-info`, or
`–template-scaffold`: those inspect the #ts-logo("LaTeX") fragment/engine machinery,
which the Typst path does not use.]

== Installing a Typst compiler

Emitting the `.typ` source never needs a compiler; compilation does. Two paths
are supported, tried in this order:

#ts-div("tab", title: "Embedded compiler (pure pip)")[
The `typst` PyPI package embeds the Rust compiler, so nothing needs to be
on your `PATH`:

```bash
pip install "texsmith[typst]"
# or
uv pip install -e ".[typst]"
# or
uv tool install "texsmith[typst]"
```]

#ts-div("tab", title: "System binary")[
Install `typst` on your `PATH` and TeXSmith detects it automatically as a
fallback:

```bash
brew install typst          # Homebrew
cargo install typst-cli      # Cargo
# or download a release from https://github.com/typst/typst/releases
```]

#ts-callout(kind: "warning", title: [Prefer the system binary for recent math])[
The compiler embedded in the `typst` PyPI package can lag behind recent
Typst releases. Math is rendered through the `mitex` package (a #ts-logo("LaTeX")-math
renderer for Typst); documents that rely on a recent `mitex` may *fail*
with the embedded compiler where an up-to-date system binary only emits a
warning. For math-heavy documents, prefer the system binary.]

If no compiler is available, the `.typ` is still written and TeXSmith reports
that compilation was skipped, with an actionable install hint.

== Scope and limitations <scope-and-limitations>

The Typst backend covers a real templated document (article and book) and the
common Markdown/HTML constructs:

- Document structure, paragraphs, and headings.
- Inline emphasis (emphasis, strong, strikeout, underline, highlight, small
caps, sub/superscript, quotes), inline code, and links.
- Code blocks, block quotes, bullet and ordered lists, definition lists,
admonitions, horizontal rules.
- Images, figures, simple (GFM) tables, and rich (`yaml` / `data-ts`) tables
rebuilt as a native Typst `#table`.
- Footnotes, #ts-logo("TeX") logos, keystrokes, progress bars.
- Math (rendered through the Typst `mitex` package) and equation
cross-references (`#ref`).
- Native citations (`#cite`) resolved against the bibliography collection the
CLI builds (`.bib` files plus inline DOI), wired through `#bibliography(...)`.

Approximated or dropped on the Typst path (no exact equivalent — the content is
preserved as closely as possible rather than producing wrong output):

- `MarginNote` renders as a `#footnote` (the `side` hint has no counterpart).
- Index entries (`<abbr>` markers) keep their visible text but emit no index
marker — Typst has no `makeindex` equivalent here.
- Remote (`http(s)://`, `data:`) or unresolved local images are dropped to keep
the document compilable.
- The #ts-logo("LaTeX")-only glossary/index engines and the fragment system are not used on
the Typst path.

Any IR node that still has *no* Typst emitter raises an explicit, localised
`TypstWriteError` (naming the node and the backend) rather than emitting wrong
output. For anything beyond this subset, use the default #ts-logo("LaTeX") backend.
