# Output backends

TeXSmith lowers every document into a typed intermediate representation (IR)
and then emits a backend from that IR:

```
read(HTML) → IR (texsmith.ir) → write(IR) → LaTeX | Typst
```

Because both backends consume the **same** IR (the readers and the IR are
untouched), you choose the output format with a single flag:

```bash
texsmith doc.md -tarticle --format latex   # default
texsmith doc.md -tarticle --format typst
```

`--format` is case-insensitive and accepts `latex` (default) or `typst`.

## LaTeX backend (default)

The LaTeX backend (`texsmith.writers.latex`) is the full-featured path: it
drives the template/fragment runtime, fonts and script matching, glossary and
index engines, asset transformers, and compiles through a TeX engine
(Tectonic by default, or `latexmk` with `--engine lualatex` / `--engine
xelatex`). This is the backend assumed throughout most of this documentation.

## Typst backend

[Typst](https://typst.app) is a modern, Rust-based typesetting system. The
Typst backend (`texsmith.writers.typst`) emits a compilable `.typ` source from
the same IR. It is a lean, Typst-native path and intentionally covers a
**subset** of the LaTeX backend (see [Scope](#scope-and-limitations)).

```bash
# Emit a .typ file (no compiler required)
texsmith doc.md -tarticle --format typst --output build/

# Emit and compile to PDF
texsmith doc.md -tarticle --format typst --build --output build/
```

Without a template, the body is wrapped in a minimal standalone preamble. With
the **article** or **book** template, the body is wrapped in the template's
Typst scaffolding (title, authors, date, abstract, table of contents,
sectioning, and a native Typst bibliography).

!!! note "Typst output and LaTeX-only flags"
    `--format typst` cannot be combined with `--html`, `--template-info`, or
    `--template-scaffold`: those inspect the LaTeX fragment/engine machinery,
    which the Typst path does not use.

### Installing a Typst compiler

Emitting the `.typ` source never needs a compiler; compilation does. Two paths
are supported, tried in this order:

=== "Embedded compiler (pure pip)"

    The `typst` PyPI package embeds the Rust compiler, so nothing needs to be
    on your `PATH`:

    ```bash
    pip install "texsmith[typst]"
    # or
    uv pip install -e ".[typst]"
    # or
    uv tool install "texsmith[typst]"
    ```

=== "System binary"

    Install `typst` on your `PATH` and TeXSmith detects it automatically as a
    fallback:

    ```bash
    brew install typst          # Homebrew
    cargo install typst-cli      # Cargo
    # or download a release from https://github.com/typst/typst/releases
    ```

!!! warning "Prefer the system binary for recent math"
    The compiler embedded in the `typst` PyPI package can lag behind recent
    Typst releases. Math is rendered through the `mitex` package (a LaTeX-math
    renderer for Typst); documents that rely on a recent `mitex` may **fail**
    with the embedded compiler where an up-to-date system binary only emits a
    warning. For math-heavy documents, prefer the system binary.

If no compiler is available, the `.typ` is still written and TeXSmith reports
that compilation was skipped, with an actionable install hint.

### Scope and limitations

The Typst backend covers a real templated document (article and book) and the
common Markdown/HTML constructs:

- Document structure, paragraphs, and headings.
- Inline emphasis (emphasis, strong, strikeout, underline, highlight, small
  caps, sub/superscript, quotes), inline code, and links.
- Code blocks, block quotes, bullet and ordered lists, definition lists,
  admonitions, horizontal rules.
- Images, figures, and simple (GFM) tables.
- Footnotes, index entries, TeX logos, keystrokes.
- Math (rendered through the Typst `mitex` package).
- Native citations (`#cite`) resolved against the bibliography collection the
  CLI builds (`.bib` files plus inline DOI), wired through `#bibliography(...)`.

Out of the covered subset (these raise an explicit error naming the node and
the backend, rather than producing wrong output):

- `MarginNote` and a few advanced nodes are **not yet supported** on the Typst
  backend.
- Rich tables (`yaml` / `data-ts` data tables) — only simple GFM tables are
  emitted.

For anything beyond this subset, use the default LaTeX backend.
