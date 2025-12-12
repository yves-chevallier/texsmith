# Supported Markdown Syntax

TeXSmith bundles Python-Markdown together with a curated set of PyMdown
extensions. The combination lets you author rich documentation while keeping
output predictable for LaTeX conversion. This page summarises the syntax you can
use out of the box and points to the extension behind each feature.

!!! info "Renderer defaults"
    The CLI and API both enable the exact same extension list defined in
    `texsmith.adapters.markdown.DEFAULT_MARKDOWN_EXTENSIONS`. You can always
    override the list with CLI flags or API options, but the features below are
    available without additional configuration.

## Core Markdown (Always On)

```markdown
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

Horizontal rules:
---
```

All standard Markdown constructs—headings, emphasis, lists, code blocks,
blockquotes, links, images, and horizontal rules—render exactly as you would
expect. TeXSmith relies on fenced code blocks by default, so triple backticks
(```` ``) are the recommended way to author code samples.

## Extension Cheat Sheet

| Feature | Extension | Package | Example |
| --- | --- | --- | --- |
| Definition lists | `def_list` | `markdown` | <code>Term<br>: Definition</code> |
| Footnotes | `footnotes` | `markdown` | <code>Footnote ref[^1]</code> |
| Abbreviations | `abbr` | `markdown` | <code>*[HTML]: HyperText Markup Language</code> |
| Admonitions | `admonition` | `markdown` | <code>!!! note<br>&nbsp;&nbsp;Body</code> |
| Attribute lists | `attr_list` | `markdown` | `![Alt](image.png){ width="50%" }` |
| Tables | `tables` | `markdown` | Pipe-delimited tables |
| Markdown in HTML | `md_in_html` | `markdown` | Markdown inside custom `<div>` blocks |
| SmartyPants | `pymdownx.smartsymbols` | `pymdown-extensions` | Auto converts quotes/dashes |
| Highlighted code | `pymdownx.highlight` | `pymdown-extensions` | Adds syntax highlighting + anchors |
| Inline highlighting | `pymdownx.inlinehilite` | `pymdown-extensions` | <code>`#!py print("hi")`</code> |
| Details/summary | `pymdownx.details` | `pymdown-extensions` | <code>???+ note "Title"</code> |
| SuperFences | `pymdownx.superfences` | `pymdown-extensions` | Nest code fences safely |
| Task lists | `pymdownx.tasklist` | `pymdown-extensions` | <code>- [x] Done</code> |
| Better emphasis | `pymdownx.betterem` | `pymdown-extensions` | Fixes edge cases with underscores |
| MagicLink | `pymdownx.magiclink` | `pymdown-extensions` | Autolinks URLs/issues |
| Keys | `pymdownx.keys` | `pymdown-extensions` | <code>++ctrl+alt+del++</code> |
| Tabbed content | `pymdownx.tabbed` | `pymdown-extensions` | Content tabs |
| Snippets | `pymdownx.snippets` | `pymdown-extensions` | Include external Markdown snippets |
| Caret mark-up | `pymdownx.caret` | `pymdown-extensions` | <code>^^insert^^</code> |
| Mark (highlight) | `pymdownx.mark` | `pymdown-extensions` | <code>==highlight==</code> |
| Tilde syntax | `pymdownx.tilde` | `pymdown-extensions` | Subscript / superscript |
| Critic mark-up | `pymdownx.critic` | `pymdown-extensions` | Editorial annotations |
| Emoji | `pymdownx.emoji` | `pymdown-extensions` | `:sparkles:` or `:fontawesome-regular-face-smile:` |
| Fancy lists | `pymdownx.fancylists` | `pymdown-extensions` | Extended list markers |
| Blocks caption | `pymdownx.blocks.caption` | `pymdown-extensions` | Captions for fenced blocks |
| Blocks HTML | `pymdownx.blocks.html` | `pymdown-extensions` | Named block wrappers |
| Snippets of LaTeX | `texsmith.latex_raw` | bundled | Raw LaTeX fence |
| Missing footnotes guard | `texsmith.missing_footnotes` | bundled | Warns when references lack definitions |

Want a generated table of contents? Add the Python-Markdown `toc` extension with `-x toc` or `--enable-extension toc`—it is no longer enabled by default.

Use the table above as a quick pointer. The following sections provide more
context and runnable examples.

## Working with Admonitions

```markdown
!!! warning "LaTeX toolchain"
    Remember to install TeX Live, MiKTeX, or MacTeX before running `texsmith --build`.
```

Admonitions render as highlighted callouts in HTML and as tcolorbox blocks in the
LaTeX output. Combine them with tabs or details blocks to create layered
walkthroughs.

## Tables and Definition Lists

```markdown
| Option | Description |
| ------ | ----------- |
| `--list-extensions` | Prints enabled Markdown extensions |
| `--debug` | Shows full tracebacks |

Term
: Definition content
```

Tables use the Python-Markdown `tables` extension while definition lists come
from `def_list`. Both convert cleanly into LaTeX environments.

## Task Lists and Checkboxes

```markdown
- [x] Validate MkDocs navigation
- [ ] Document template slots
```

Task lists automatically render checkboxes in HTML. In LaTeX they become custom
itemize entries with inline symbols.

## Keyboard Shortcuts

```markdown
Use ++ctrl+s++ to save changes and ++ctrl+shift+b++ to build the docs.
```

The `pymdownx.keys` extension turns the markup above into keyboard glyphs, which
carry across to PDFs through the TeXSmith formatter.

## Embedding Raw LaTeX

Use the `/// latex` fence when native LaTeX is required:

```markdown
/// latex
\begin{align}
E &= mc^2 \\
\nabla \cdot \vec{E} &= \frac{\rho}{\varepsilon_0}
\end{align}
///
```

TeXSmith passes the block straight to the renderer, letting you mix handcrafted
LaTeX with converted Markdown content. For inline adjustments drop
`{latex}[commands]` right into the paragraph:

```markdown
The chapter ends here {latex}[\clearpage] before appendices.
```

## Snippet Includes

The `pymdownx.snippets` extension lets you avoid duplication:

```markdown
;--8<-- "includes/built-in-tasks.md"
```

Create an `includes` directory under `docs/` and share fragments across pages.
The same mechanism can pull example Markdown from the samples used in automated
tests, keeping docs and fixtures aligned.

## When You Need More

- Use `texsmith --list-extensions` to see the live extension list.
- Disable or add extensions via the `--enable-extension` and `--disable-extension`
  flags in `texsmith` or through `ConversionRequest.markdown_extensions`
  in the API.
- If a feature relies on a third-party executable (for example Mermaid to PDF),
  make sure the binary is available on the build worker before running
  `texsmith --build`.

With these extensions enabled, TeXSmith can faithfully render everything from
simple README-style guides to complex, reference-heavy manuals.
