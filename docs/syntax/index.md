# Markdown

If Markdown is new to you, start with the [canonical guide](https://www.markdownguide.org/basic-syntax/).

The original spec is spartan—tables, diagrams, and other niceties didn’t exist.

Over time new *flavours* sprouted to fill the gaps. Because TeXSmith targets MkDocs, it aligns with [Python-Markdown](https://python-markdown.github.io/extensions/) (MkDocs’ engine) plus the usual suspects like [Pymdown Extensions](https://facelessuser.github.io/pymdown-extensions/).

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

So many flavours, so many extensions, so many incompatible syntaxes—it’s a jungle. CommonMark tried to herd the cats and mostly succeeded, but fragmentation remains. MyST brought Sphinx-style goodies to Markdown, yet it isn’t MkDocs-compatible, so TeXSmith had to chart its own course.

[![How Standards Proliferate](../assets/standards.svg){width=60%}](https://imgs.xkcd.com/comics/standards.png)

Source: xkcd[^1].

[^1]: [xkcd:927](https://xkcd.com/927/)

TeXSmith is unapologetically opinionated: it curates a stack, sprinkles extra sauce on top, and calls the bundle **Tmark** (TeXSmith Markdown).
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
| Index Entries | `{index}[entry]` (use `{index:registry}[entry]` to target another registry; add more `[level]` brackets for nesting) | `texsmith.index`        |
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

## Default Extensions

- Python Markdown
  - abbr
  - admonition
  - attr_list
  - def_list
  - footnotes
  - smarty
  - tables
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
