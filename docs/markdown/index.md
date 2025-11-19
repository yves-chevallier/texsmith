# Markdown

If you don't know Markdown, you should probably start with the [official documentation](https://www.markdownguide.org/basic-syntax/).

Markdown was designed to be minimalist and back then didn't include features for embedding complex content (tables, diagrams...).

Various *flavours* of Markdown have since emerged, each extending the original syntax in different ways. As we target MkDocs, TeXSmith supports the same extensions as [Python-Markdown](https://python-markdown.github.io/extensions/), which is the engine behind MkDocs and the majority of Markdown extensions such as [Pymdown Extensions](https://facelessuser.github.io/pymdown-extensions/).

For printed documentation, especially for scientific or technical reports, some additional features are required:

- Citations and bibliographies
- Cross-references
- Diagrams (Mermaid, Graphviz, Vega)
- Mathematical formulas (LaTeX math)
- Index
- Glossary and acronyms
- Rich tables (span, multi-line cells, etc.)
- Direct LaTeX injections using fenced `/// latex` blocks or inline `{latex}[...]` snippets that stay hidden in HTML but reach the LaTeX output unchanged

## Markdown is a mess

So many flavours, so many extensions, so many incompatible syntaxes. It's a jungle out there! Some attempted to standardize Markdown (CommonMark) but the ecosystem is still fragmented. A nice shot was MyST which tried to bring Sphinx-style reStructuredText features to Markdown, but it is not compatible with MkDocs and thus not supported by TeXSmith.

![How Standards Proliferate[^1]](https://imgs.xkcd.com/comics/standards.png)

*[1]: [xkcd:927](https://xkcd.com/927/)

So as an opinionated tool, TeXSmith picks a set of extensions, adds a few more, and call it: **Tmark** (for TeXSmith Markdown).
## TeXSmith compatibility

### Commonmark

[CommonMark](https://commonmark.org/help/) is the standardized, modern version of Markdown.

| Feature          | Syntax        | Supported |
| ---------------- | ------------- | --------- |
| Italic           | `*x*`         | Yes       |
| Bold             | `**x**`       | Yes       |
| Heading          | `# H`         | Yes       |
| Links            | `[Text](url)` | Yes       |
| Images           | `![Alt](url)` | Yes       |
| Inline Code      | `` `code` ``  | Yes       |
| Footnotes        | `^[1]`        | Yes       |
| Tables           |               | Yes       |
| Blockquotes      | `> Quote`     | Yes       |
| Ordered Lists    | `1. Item`     | Yes       |
| Unordered Lists  | `- Item`      | Yes       |
| Horizontal Rules | `---`         | Yes       |
| Superscript      | `^x^`         | Yes       |
| Subscript        | `~x~`         | Yes       |
| Strikethrough    | `~~x~~`       | Yes       |

### GitHub Flavored Markdown (GFM)

[GFM](https://github.github.com/gfm/) is the version of Markdown used by GitHub, which extends CommonMark with additional features.

| Feature   | Syntax       | Supported |
| --------- | ------------ | --------- |
| Separator | `***`, `___` | Yes       |

### Python Markdown

[Python-Markdown](https://python-markdown.github.io/) is the Markdown engine used by MkDocs. It extends CommonMark with a variety of features through extensions.

| Feature          | Syntax                      | Extension    | Supported |
| ---------------- | --------------------------- | ------------ | --------- |
| Definition Lists | `: def`                     | `def_list`   | Yes       |
| Admonitions      | `!!! note`                  | `admonition` | Yes       |
| Inline Math      | `$\sqrt{x}$`                | `mdx_math`   | Yes       |
| SmartyPants      | `<< >>`, `...`, `--`, `---` | `smarty`     | Yes       |
| WikiLinks        | `[[Wiki link]]`             | `wikilinks`  | Yes       |

### PyMdown Extensions

[Pymdown Extensions](https://facelessuser.github.io/pymdown-extensions/) is a popular collection of Markdown extensions for Python-Markdown, which adds many useful features.

| Feature              | Syntax                      | Extension               | Supported |
| -------------------- | --------------------------- | ----------------------- | --------- |
| Better Emphasis      | `***x***`                   | `pymdownx.betterem`     | Yes       |
| Superscript          | `x^2^`                      | `pymdownx.caret`        | Yes       |
| Underline            | `^^x^^`                     | `pymdownx.caret`        | Yes       |
| Strikethrough        | `~~x~~`                     | `pymdownx.tilde`        | Yes       |
| Collapsible Sections | `??? note`                  | `pymdownx.details`      | Yes       |
| Emoji                | `:smile:`                   | `pymdownx.emoji`        | Yes       |
| Code Highlight       | `` `#!php echo "Hello";` `` | `pymdownx.inlinehilite` | Yes       |
| Keys                 | `++ctrl+a++`                | `pymdownx.keys`         | Yes       |
| Magic Links          | `https://acme.com`          | `pymdownx.magiclink`    | Yes       |
| Highlight            | `==x==`                     | `pymdownx.mark`         | Yes       |
| Smart Symbols        | `(c)`                       | `pymdownx.smartsymbols` | Yes       |
| Task Lists           | `- [ ]`                     | `pymdownx.tasklist`     | Yes       |

### TeXSmith Extensions

| Feature       | Syntax                    | Extension               |
| ------------- | ------------------------- | ----------------------- |
| Small Caps    | `^^x^^`                   | `texsmith.smallcaps`    |
| Mermaid       | `![](diagram.mmd)`        | `texsmith.mermaid`      |
| Progress Bars | `[=75% "Done"]`           | `texsmith.progressbar`  |
| Bibliography  | `[^citekey]`              | `texsmith.bibliography` |
| Index Entries | `#[entry]`                | `texsmith.index`        |
| Acronyms      | `ACME (Acme Corporation)` | `texsmith.acronyms`     |
| Raw LaTeX     | `/// latex`, `{latex}[x]` | `texsmith.latex_raw` / `texsmith.rawlatex` |
| LaTeX Text    | `LaTeX`, `TeXSmith`       | `texsmith.latex`        |

### Other

| Cross-references         |               |  Yes       |
| Mermaid Diagrams         |               |  Yes       |
| Graphviz Diagrams        |               |  Yes       |
| Vega Diagrams            |               |  Yes       |
| Svgbob Diagrams          |               |  Yes       |
| CircuitTikZ Diagrams     |               |  Yes       |

## Defaults Extensions

- Python Markdown
  - abbr
  - admonition
  - attr_list
  - def_list
  - footnotes
  - smarty
  - tables
  - toc
  - mdx_math
  - md_in_html
- TeXSmith
  - texsmith.multi_citations:MultiCitationExtension
  - texsmith.latex_raw:LatexRawExtension
  - texsmith.missing_footnotes:MissingFootnotesExtension
  - texsmith.latex_text:LatexTextExtension
  - texsmith.smallcaps:SmallCapsExtension
  - texsmith.progressbar:ProgressBarExtension
- Pymdown Extensions
  - pymdownx.betterem
  - pymdownx.blocks.caption
  - pymdownx.blocks.html
  - pymdownx.caret
  - pymdownx.critic
  - pymdownx.details
  - pymdownx.emoji
  - pymdownx.fancylists
  - pymdownx.highlight
  - pymdownx.inlinehilite
  - pymdownx.keys
  - pymdownx.magiclink
  - pymdownx.mark
  - pymdownx.saneheaders
  - pymdownx.smartsymbols
  - pymdownx.snippets
  - pymdownx.superfences
  - pymdownx.tabbed
  - pymdownx.tasklist
  - pymdownx.tilde

## Raw LaTeX Snippets (`/// latex`, `{latex}[...]`)

When you need to insert LaTeX that must not appear in the HTML build, use the dedicated fence:

```md
/// latex
\newcommand{\R}{\mathbb{R}}
///
```

For inline tweaks, drop `{latex}[payload]` anywhere inside your paragraph:

```md
Section break {latex}[\clearpage] before the next topic.
```

Both syntaxes create hidden nodes (`<p>` for blocks, `<span>` for inline) so the fragments remain invisible online. During the HTML → LaTeX conversion, TeXSmith spots these nodes and drops the original payload straight into the final document. This makes it safe to declare macros, page tweaks, or any advanced snippet without impacting the web version.
