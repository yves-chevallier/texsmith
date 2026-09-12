# Supported Markdown Syntax

TeXSmith reads [TMark](index.md): CommonMark plus the extension set every
MkDocs site already loads, plus the four families that cover what print needs.
This page is the quick tour; each row links to the page that explains the
construct.

!!! info "One dialect, no configuration"
    There is no extension list to enable. The parser is the same for the CLI,
    the Python API and the MkDocs plugin, and `tmark check FILE` tells you
    exactly what it read.

## Core Markdown (Always On)

```md
# Heading 1
## Heading 2
### Heading 3

**bold**, *italic*, ~~strikethrough~~, `inline code`

[Links](https://www.example.com) and ![images](assets/logo.svg)

> Blockquote text

- Unordered item
  - Nested item

1. Ordered item
2. Next item

Dividers:

---
```

All standard CommonMark constructs render as you would expect. A `---` line is
a **divider**: the web shows `<hr>`, and the paged writers emit `\tsdivider`,
which the `ts-typesetting` fragment defines as a page break — a template
redefines it at will. Inside a container — a block quote, a callout, a figure,
a `:::` div, a list item — the same `---` emits `\tsrule` instead (`<hr
class="rule">` on the web): a separator, never a page break, because a page
break there would tear the container in two.

## Cheat sheet

| Feature | Canonical spelling | Class |
| --- | --- | --- |
| Definition lists | <code>Term<br>: Definition</code> | E |
| Footnotes | `[^1]` with a `[^1]: …` definition | C |
| Abbreviations | `*[HTML]: HyperText Markup Language` | E |
| Callouts | `::: note {title="…"}` (sugar `!!! note "…"`) | D / E |
| Collapsible callouts | `::: note {collapsed=true}` (sugar `??? note`) | D / E |
| Attribute lists | `![Alt](image.png){width=50%}` | E |
| Tables | pipe tables, ```` ```yaml table ```` | C / D |
| Captions | `Figure: … {#fig:x}` after the float | D |
| Containers | `::: div`, `::: multicolumn {cols=2}`, `::: figure` | D |
| Content tabs | `::: tabs` + `::: tab {title=…}` (sugar `=== "…"`) | D / E |
| Highlighted code | ```` ```py title="x.py" linenums="1" ```` | E |
| Inline highlighting | `` `#!py print("hi")` `` or `{code py}[print(1)]` | E |
| Task lists | `- [x] Done` | C |
| Keys | `{keys}[ctrl+alt+del]` (sugar `++ctrl+alt+del++`) | E |
| Highlight | `{mark}[x]` (sugar `==x==`) | E |
| Small caps | `{sc}[x]` (sugar `__x__`) | X1 |
| Subscript / superscript | `{sub}[x]` / `{sup}[x]` (sugar `~x~`, `^x^`) | X3 / E |
| Emoji | `:sparkles:` | E |
| Material icons | `:material-cog:` (web only) | D |
| Smart symbols | `(c)`, `-->`, `1/2` | E |
| Quotes | `"a phrase"` → `\enquote{…}` | C |
| Insert | `{underline}[x]` (sugar `^^x^^`, feature `inline.insert`) | D |
| Unnumbered heading | `# Preface {.unnumbered}` / `{.unlisted}` — [Headings](headings.md) | E |
| Anchor on a phrase | `[this claim]{#claim:one}` | D |
| Autolinks | bare URLs | E |
| Critic markup | `{++added++}`, `{--removed--}` | E |
| Math | `$x$`, `$$…$$ {#eq:x}` | C |
| Progress bars | `[=75% "Done"]` | E |
| Index entries | `{index}[term]`, `#[term]` | X5 |
| Counter items | `#(fw:key)` | X5 |
| References & citations | `@key`, `@[key, p. 3]` | X4 |
| Glossary references | `@gls:term` | D |
| Asides / margin notes | `{aside}[…]`, `::: aside` | D |
| Raw passthrough | `{raw latex}(…)`, ```` ```latex raw ```` | D |
| Includes | `{include}(file.md)` | D |
| Diagrams | `![Pipeline](pipeline.mmd)`, ```` ```mermaid image ```` | C / E |
| Foreign directives | `[TOC]`, `::: pkg.module` (kept verbatim, dropped in print) | E / D |

Classes are the degradation classes of [TMark](index.md#degradation-classes):
what a renderer other than TeXSmith shows for the same bytes.

## Working with callouts

```md
::: warning {title="LaTeX toolchain"}
Remember to install TeX Live, MiKTeX, or MacTeX before running `texsmith --build`.
:::
```

The PyMdownX spelling stays accepted indefinitely, because MkDocs Material
renders it natively:

```md
!!! warning "LaTeX toolchain"
    Remember to install TeX Live, MiKTeX, or MacTeX before running `texsmith --build`.
```

Callouts render as highlighted boxes in HTML and as `tcolorbox` blocks in the
LaTeX output. See [Admonitions](admonitions.md).

## Tables and definition lists

```md
| Option | Description |
| ------ | ----------- |
| `--debug-ir` | Dumps the parsed IR next to the output |
| `--debug` | Shows full tracebacks |

Table: Selected command-line options. {#tbl:options}

Term
: Definition content
```

Both convert cleanly into LaTeX environments. For spans, grouped headers,
footers and validation, see [Tables](tables.md).

## Task lists and checkboxes

```md
- [x] Validate MkDocs navigation
- [ ] Document template slots
```

Task lists render checkboxes in HTML. In LaTeX they become `tstasklist` entries
with inline symbols.

## Keyboard shortcuts

```md
Use {keys}[ctrl+s] to save changes and {keys}[ctrl+shift+b] to build the docs.
```

The PyMdownX spelling `++ctrl+s++` is sugar for the same node and renders
identically. Both reach the PDF as `\tskeys{…}`.

## Embedding raw LaTeX

Use a `latex raw` fence when native LaTeX is required:

````md
```latex raw
\begin{align}
E &= mc^2 \\
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0}
\end{align}
```
````

TeXSmith passes the block straight to the LaTeX writer; the Typst and HTML
writers ignore it. For inline adjustments, use the `raw` role:

```md
The chapter ends here {raw latex}(\clearpage) before appendices.
```

`/// latex … ///` and `{latex}[…]` are the 0.6 spellings: still parsed, now
deprecated. See [Migrating to TMark](../guide/migration.md).

## Includes

```md
{include}(includes/built-in-tasks.md)
```

The file is parsed as TMark and spliced into the document, so nested fences are
safe and relative paths inside it are rebased. To pull a code sample from a
file without inlining it, put `include=` on the fence:

````md
```python include="examples/code/bubble_sort.py"
```
````

The PyMdownX snippet syntax `--8<-- "file"` is accepted as deprecated sugar.
Its marker is `-{2,}8<-{2,}`, so any dash count on either side is the same
spelling (`---8<---` included), and a leading `;` disables the line. See
[Code](code.md#external-sources).

## Foreign directives

`[TOC]` and a **dotted** `::: pkg.module` line — mkdocstrings' syntax, its
options in the indented YAML that follows — are directives for a processor
other than TMark. Both are kept verbatim, and both are **dropped by the paged
writers**: the printed table of contents is `press.toc`, and an API reference
has no print form. A dotted directive raises the hint `directive-foreign` so a
print document does not lose a block without notice. See
[Admonitions](admonitions.md#foreign-directives).

## When you need more

- `tmark check FILE` parses, resolves and lints a document; `--strict` turns
  warnings into failures.
- `tmark lint --fix FILE` rewrites deprecated spellings.
- `tmark parse FILE` prints the intermediate representation as JSON — the
  ground truth about what the parser read.
- If a feature relies on a third-party executable (Mermaid to PDF, draw.io
  export), make sure the binary is available on the build worker before running
  `texsmith --build`.
