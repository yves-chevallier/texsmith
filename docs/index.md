
## Key Features

- **Markdown to LaTeX Conversion**: Converts standard and extended Markdown syntax into LaTeX.
- **MkDocs Integration**: Seamlessly supports MkDocs HTML output to generate LaTeX documents from documentation sites through a dedicated MkDocs plugin.
- **Extended Markdown Support**: Handles various Markdown extensions including tables, footnotes, code blocks, footnotes, abbreviations, and more.
- **Bibliography Management**: Supports citation and bibliography generation using BibTeX.
- **Cross-Referencing**: Enables cross-referencing of sections, figures, tables, and equations within the document.
- **Customizable Output**: Allows users to customize the LaTeX output through templates.
- **Command-Line Interface**: Provides a user-friendly CLI for easy conversion of Markdown files to LaTeX.
- **Lightweight**: Does not require heavy dependencies, making it easy to install and use in pure Python environments [^1].

[^1]: Note that for full functionality, especially bibliography management, a LaTeX distribution is still required to build the final PDF document.

## Getting Started

To install TeXSmith, you can use pip:

```bash
pip install texsmith
```

```bash
$ cat << EOF > doc.md
# Quadratic Equation

The solution to the **quadratic equation** [^1] is given by:

$$
x_{1,2} = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$

[^1]: A polynomial equation of the second degree.
EOF

$ texsmith doc.md
\section{Quadratic Equation}

The solution to the \textbf{quadratic equation} \footnote{A polynomial equation of the second degree.} is given by:

$$
x_{1,2} = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$
```

## Develop your own templates

TeXSmith uses Jinja2 templates to define the structure of the generated LaTeX documents. You can create your own templates by first generating a default skeleton template:

```bash
texsmith create-template my_template
```

Templates are made to be deployed to PyPI as separate packages, so that they can be installed and used easily. For more information on creating and publishing templates, please refer to the documentation.

## Specialized Markdown for LaTeX

When writing LaTeX documents (articles, reports, books...) in Markdown, you may be limited by seveal missing features such as:

- Figure and table captions
- Bibliography entries
- Acronyms and Glossary
- Index generation
- Part/chapter/section management
- Placement of sections (frontmatter, mainmatter, appendix...)
- Force a new page

For these we have defined easy workarounds that is meant to not pollute the Markdown syntax too much.

### Figure and Table Captions

```md
![This is a caption]{fig.png}


| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
{: caption="This is a caption" }
```

### Bibliography Entries

```md
Einstein's relativity theory [^einstein1905] is a cornerstone of modern physics.
```

### Acronyms

```md
The CPU (Central Processing Unit) is the brain of the computer.


## Behind the hood

TeXSmith is built using Python Markdown with the following extensions enabled by default: `abbr`, `admonition`, `attr_list`, `def_list`, `footnotes`, `md_in_html`, `mdx_math`, `pymdownx.betterem`, `pymdownx.blocks.caption`, `pymdownx.blocks.html`, `pymdownx.caret`, `pymdownx.critic`, `pymdownx.details`, `pymdownx.emoji`, `pymdownx.fancylists`, `pymdownx.highlight`, `pymdownx.inlinehilite`, `pymdownx.keys`, `pymdownx.magiclink`, `pymdownx.mark`, `pymdownx.saneheaders`, `pymdownx.smartsymbols`, `pymdownx.snippets`, `pymdownx.superfences`, `pymdownx.tabbed`, `pymdownx.tasklist`, `pymdownx.tilde`, `tables`, `toc`.

The **renderer** works by traversing the generated HTML tree with BeautifulSoup and converting each element to its LaTeX equivalent. This curious design choice was made to ensure compatibility with some MkDocs plugins that modify the HTML output directly. Therefore some plugins can sometime lead to unexpected behaviors, so please report any issues you may encounter.

At runtime the orchestration is handled by `ConversionService`. `ConversionRequest` instances capture every input (documents, slot directives, render options, bibliography files) and `ConversionResponse` reports the rendered bundle plus diagnostics emitted through the new `DiagnosticEmitter` interface. Slot mapping is handled uniformly via `DocumentSlots`, and templates go through a dedicated `TemplateRenderer` so both single- and multi-document workflows share the same code path.
