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
- Direct LaTeX injections using fenced `/// latex` blocks that stay hidden in HTML but reach the LaTeX output unchanged

## Raw LaTeX Blocks (`/// latex`)

When you need to insert LaTeX that must not appear in the HTML build, use the dedicated fence:

```md
/// latex
\newcommand{\R}{\mathbb{R}}
///
```

The Markdown → HTML pass creates a hidden paragraph (`<p class="latex-raw" style="display:none;">…</p>`) so the fragment remains invisible online. During the HTML → LaTeX conversion, TeXSmith spots these blocks and drops the original payload straight into the final document. This makes it safe to declare macros, page tweaks, or any advanced snippet without impacting the web version.
