#set document(
  title: "TeXSmith Markdown Syntax",
  author: ("Yves Chevallier",),
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
  #text(size: 1.8em, weight: "bold")[TeXSmith Markdown Syntax]
]
#align(center)[
  Yves Chevallier]
#v(1.5em)

#block(width: 100%, inset: (x: 2em))[
  #align(center)[#text(weight: "bold")[Abstract]]
  #v(0.5em)
This document provides a comprehensive overview of Markdown syntax features and extensions supported by TeXSmith. It serves as a reference guide for users looking to leverage Markdown's capabilities in their documents. This is meant to be a cheatsheet of supported features and a test suite for custom templates.
]
#v(1em)

#outline()
#v(1em)

= Core Markdown (Standard "Vanilla")

== Headings

Demonstrates the Markdown heading hierarchy from level 1 to level 5. Note that in Markdown only six levels are defined: `#` to `######`. In LaTeX, however, there are less levels (e.g., `\section`, `\subsection`, `\subsubsection`, `\paragraph`, `\subparagraph`). The last one is usually simply converted to bold text.

```md
# Heading 1

Lorem ipsum dolor sit amet.

## Heading 2

Lorem ipsum dolor sit amet.

### Heading 3

Lorem ipsum dolor sit amet.

#### Heading 4

Lorem ipsum dolor sit amet.

##### Heading 5

Lorem ipsum dolor sit amet.
```

== Bold

Shows how to emphasise text with bold weight. Simply translated to `\textbf{…}` in LaTeX.

```md
**text** or **t**ex**t**
```

#quote(block: true)[
  *text* or *t*ex*t*
]

== Italic

Applies emphasis for terminology or voice.

```md
This _text_ or *text* is italic.
```

#quote(block: true)[
  This _text_ or _text_ is italic.
]

== Strikethrough

Marks text as deleted or obsolete.

```md
We ~~do not~~ want this.
```

#quote(block: true)[
  We #strike[do not] want this.
]

== Underline

With caret, mark and tilde extension from PyMdownX it is also possible to underline text.

```md
^^text^^
```

#quote(block: true)[
  #underline[text]
]

== Inline Code / Code Blocks

````md
This entry is `inline code`, or can be in a fenced code block:

```python
print("Hello")
```
````

#quote(block: true)[
  This entry is `inline code`, or can be in a fenced code block:

  ```python
  print("Hello")
  ```
]

== Hyperlinks

Creates external hyperlinks, in PDF converted to clickable links.

```md
The German-bord pysicist [Albert Einstein](https://en.wikipedia.org/wiki/Albert_Einstein) is famous for
his nobel prize and the theory of relativity.
```

#quote(block: true)[
  The German-bord pysicist #link("https://en.wikipedia.org/wiki/Albert_Einstein")[Albert Einstein] is famous for
  his nobel prize and the theory of relativity.
]

== Images

Embeds remote or local images.

```md
![Random Picture](https://picsum.photos/500/200)
```

#quote(block: true)[

]

== Lists

== Bulleted Lists

```md
- First
- Second
    - Subitem
```

#quote(block: true)[
  - First
  - Second
    - Subitem
]

== Enumerated Lists

```md
1. Numbered first
2. Numbered second
    1. Sub-numbered
        a. Sub-sub-numbered
        b. Sub-sub-numbered
    2. Sub-numbered
```

#quote(block: true)[
  + Numbered first
  + Numbered second
    + Sub-numbered
      + Sub-sub-numbered
      + Sub-sub-numbered
    + Sub-numbered
]

== Blockquotes

Highlights quotations or cited text.

```md
> Quote
```

#quote(block: true)[
  Quote
]

== Horizontal Rules

Adds a visual separator between sections.

```md
-----
```

#quote(block: true)[
  #line(length: 100%)
]

= TeXSmith Markdown Extensions

TeXSmith features several custom Markdown extensions to enhance document authoring.
Below is a summary of the supported extensions along with their usage.

== Small Capitals

With standard Markdown `**` or `__` have the same effect as bold while the former is usually preferred. TeXSmith uses the latter for small capitals when the `texsmith.smallcaps`
extension is enabled.

```md
This is __small capitals__.
```

#quote(block: true)[
  This is #smallcaps[small capitals].
]

= Advanced Syntax Extensions (Non-Standard)

== Tables

```md
| Column 1 | Column 2 |
| -------- | -------- |
| Value 1  | Value 2  |
| Value 3  | Value 4  |
```

#quote(block: true)[
  #table(
    columns: 2,
    align: (left, left),
    table.header([Column 1], [Column 2]),
    [Value 1], [Value 2],
    [Value 3], [Value 4],
  )
]

== Footnotes

A footnote is a note placed at the bottom of the page.

```md
Text with note[^1].

[^1]: Here is the note.
```

#quote(block: true)[
  Text with note#footnote[Here is the note.].
]

== Abbreviations

_Extension: `abbr`_
_Package: `markdown` (standard)_
_Description: Expands acronyms on hover._

```md
The HTML standard.

*[HTML]: HyperText Markup Language
```

#quote(block: true)[
  The HTML standard.
]

== Definition Lists

_Extension: `definition_lists`_
_Package: `markdown` (standard)_
_Description: Pairs terms with their definitions._

```md
Term
: Definition of the term

Another term
:   Another definition with a longer description that spans
    multiple lines and
    is indented properly.
```

#quote(block: true)[
  / Term: Definition of the term
  / Another term: Another definition with a longer description that spans
  multiple lines and
  is indented properly.
]

== Admonitions (Alert / Info / Tip Blocks)

_Extension: `admonition`_
_Package: `pip install markdown` or `pymdown-extensions` (for advanced styles)_
_Description: Emphasises callouts such as notes and warnings._

```md
!!! note
    This is a note.

??? warning
    This is a warning.
```

The `???` syntax creates a collapsible block in HTML output only.

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
  #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)Note]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    This is a note.
  ]
]

#block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#FFB200"), rest: 0.4pt + rgb("#FFB200")))[
  #block(width: 100%, fill: rgb("#FFB200").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#FFB200"))[⚠#h(0.4em)Warning]]
  #block(width: 100%, inset: (x: 8pt, y: 6pt))[
    This is a warning.
  ]
]

== SuperFences (Enhanced Fenced Code + Nested Blocks)

_Extension: `pymdownx.superfences`_
_Package: `pip install pymdown-extensions`_
_Description: Allows nested fences (e.g., Mermaid diagrams inside fences)._

````md
```mermaid { width=20% }
graph TD;
  A-->B;
```
````

#quote(block: true)[
  #image("<HASH>.png")
]

== Raw LaTeX Blocks and Inline Snippets

_Extension: `texsmith.markdown_extensions.latex_raw`_
_Package: shipped with TeXSmith_
_Description: Embeds raw LaTeX that is injected verbatim._

```md
\clearpage
```

Inline variant:

```md
Insert... {latex}[\clearpage] anywhere in the paragraph.
```

Insert...  anywhere in the paragraph.

== Emoji

_Extension: `pymdownx.emoji`_
_Package: `pip install pymdown-extensions`_
_Description: Converts shortcodes into emoji._

```md
:smile:
:heart:
```

#quote(block: true)[
  😄
  ❤️
]

You can also use Unicode emoji directly (not currently supported in mono environments). It will use OpenMoji black by default in TeXSmith unless you specify another font for emoji in the configuration.

```md
😊 🚀 🍕 🎉 🐍 🌍 💻
📚 🎨 👽 👋 🤖 🦄 🧠
```

#quote(block: true)[
  😊 🚀 🍕 🎉 🐍 🌍 💻
  📚 🎨 👽 👋 🤖 🦄 🧠
]

== Task Lists

_Extension: `pymdownx.tasklist`_
_Package: `pip install pymdown-extensions`_
_Description: Creates interactive checklists._

```md
- [x] Done
- [ ] To do
```

#quote(block: true)[
  - Done
  - To do
]

== Highlight / Mark

_Extension: `pymdownx.mark`_
_Package: `pip install pymdown-extensions`_
_Description: Highlights text with a marker effect._

```md
==Cellular respiration is a set of metabolic reactions== that take place
in the cells of organisms. Its ==primary== function is to convert
biochemical energy from nutrients into ==adenosine triphosphate (ATP)==,
and then release waste products.
```

#quote(block: true)[
  #highlight[Cellular respiration is a set of metabolic reactions] that take place in the
  cells of organisms. Its #highlight[primary] function is to convert biochemical energy
  from nutrients into #highlight[adenosine triphosphate (ATP)], and then release waste
  products.
]

== Tilde / Subscript / Superscript

_Extension: `pymdownx.tilde`, `pymdownx.caret`_
_Package: `pip install pymdown-extensions`_
_Description: Adds subscripts and superscripts._

```md
H~2~O, E = mc^2^

H₂O, E = mc²
```

#quote(block: true)[
  H#sub[2]O, E = mc#super[2]

  H₂O, E = mc²
]

== SmartSymbols

_Extension: `pymdownx.smartsymbols`_
_Package: `pip install pymdown-extensions`_
_Description: Automatically substitutes typographic punctuation._

```md
"Smart quotes", ellipses..., en-dash --, em-dash ---
```

#quote(block: true)[
  "Smart quotes", ellipses..., en-dash –, em-dash —
]

== Better Math / LaTeX

_Extension: `pymdownx.arithmatex`_
_Package: `pip install pymdown-extensions`_
_Rendering engines: depends on KaTeX or MathJax._
_Description: Typesets mathematical formulas with LaTeX syntax._

```md
The differential form of Maxwell's equations:

$$
\begin{aligned}
\nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
\nabla \cdot \mathbf{B} &= 0 \\
\nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
\nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0
\frac{\partial \mathbf{E}}{\partial t}
\end{aligned}
$$
```

#quote(block: true)[
  The differential form of Maxwell's equations:

  #mitex(```\begin{aligned}
  \nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
  \nabla \cdot \mathbf{B} &= 0 \\
  \nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
  \nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0
  \frac{\partial \mathbf{E}}{\partial t}
  \end{aligned}```)
]

== MagicLink (Automatic GitHub / Issue Links)

_Extension: `pymdownx.magiclink`_
_Package: `pip install pymdown-extensions`_
_Description: Auto-links URLs, emails, GitHub references, and more._

```md
https://github.comuser/project#1
```

#quote(block: true)[
  #link("https://github.comuser/project#1")[https://github.comuser/project\#1]
]

== ProgressBar

_Extension: `pymdownx.progressbar`_
_Package: `pip install pymdown-extensions`_
_Description: Visualises progress as textual bars._

```markdown
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{: .thin}
```

#box(width: 9cm, height: 12pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 25%, height: 100%, fill: luma(40%))[]] Research

#box(width: 9cm, height: 12pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 50%, height: 100%, fill: luma(40%))[]] Implementation

#box(width: 9cm, height: 12pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 75%, height: 100%, fill: luma(40%))[]] Review

#box(width: 9cm, height: 6pt, radius: 1pt, stroke: 0.5pt, fill: luma(90%), clip: true)[#box(width: 100%, height: 100%, fill: luma(40%))[]] Launch

== Details / Collapsible Blocks

_Extension: `pymdownx.details`_
_Package: `pip install pymdown-extensions`_
_Description: Creates collapsible disclosure sections._

```md
???+ note "Title"

    Collapsible content.
```

#quote(block: true)[
  #block(width: 100%, radius: 2pt, stroke: (left: 1.5pt + rgb("#448AFF"), rest: 0.4pt + rgb("#448AFF")))[
    #block(width: 100%, fill: rgb("#448AFF").lighten(90%), inset: (x: 8pt, y: 4pt))[#text(weight: "bold", fill: rgb("#448AFF"))[📝#h(0.4em)Title]]
    #block(width: 100%, inset: (x: 8pt, y: 6pt))[
      Collapsible content.
    ]
  ]
]

== Keys (Keyboard Display)

_Extension: `pymdownx.keys`_
_Package: `pip install pymdown-extensions`_
_Description: Shows keyboard shortcuts with consistent styling._

```md
++Ctrl+C++
```

#quote(block: true)[
  #box(stroke: 0.5pt, inset: (x: 3pt), outset: (y: 2pt))[control]+#box(stroke: 0.5pt, inset: (x: 3pt), outset: (y: 2pt))[c]
]

== Tab Blocks (Tabbed Content)

_Extension: `pymdownx.tabbed`_
_Package: `pip install pymdown-extensions`_
_Description: Groups content in tabbed panes._

```md
=== "Windows"

Windows is a Microsoft operating system.

=== "Linux"

Linux is an open-source operating system.
```

Windows is a Microsoft operating system.

Linux is an open-source operating system.

== Meta-Data / Front Matter

_Extension: `meta`_
_Package: `markdown` (standard)_
_Description: Adds YAML metadata at the beginning of a document._

```md
---
Title: My document
Author: Alice
---

# Title
```

== Snippets

_Extension: `pymdownx.snippets`_
_Package: `pymdown-extensions`_
_Description: Includes content from other Markdown files._

Permits you to include content from other Markdown files.

````md
```python
from __future__ import annotations

from collections.abc import Iterable

Move = tuple[int, str, str]

def tower_of_hanoi(n: int, source: str, destination: str, auxiliary: str) -> list[Move]:
    """Compute the move sequence for the Tower of Hanoi puzzle."""
    moves: list[Move] = []

    def _solve(disks: int, start: str, end: str, spare: str) -> None:
        if disks == 0:
            return
        _solve(disks - 1, start, spare, end)
        moves.append((disks, start, end))
        _solve(disks - 1, spare, end, start)

    _solve(n, source, destination, auxiliary)
    return moves

def render_solution(moves: Iterable[Move]) -> str:
    """Return a human-readable description of the move sequence."""
    return "\n".join(
        f"Move disk {disk} from source {start} to destination {end}" for disk, start, end in moves
    )

```
````

```python
from __future__ import annotations

from collections.abc import Iterable

Move = tuple[int, str, str]

def tower_of_hanoi(n: int, source: str, destination: str, auxiliary: str) -> list[Move]:
    """Compute the move sequence for the Tower of Hanoi puzzle."""
    moves: list[Move] = []

    def _solve(disks: int, start: str, end: str, spare: str) -> None:
        if disks == 0:
            return
        _solve(disks - 1, start, spare, end)
        moves.append((disks, start, end))
        _solve(disks - 1, spare, end, start)

    _solve(n, source, destination, auxiliary)
    return moves

def render_solution(moves: Iterable[Move]) -> str:
    """Return a human-readable description of the move sequence."""
    return "\n".join(
        f"Move disk {disk} from source {start} to destination {end}" for disk, start, end in moves
    )
```

== EscapeAll

_Extension: `pymdownx.escapeall`_
_Package: `pymdown-extensions`_
_Description: Forces every Markdown character to be escaped._

Forces the escaping of special Markdown characters.

== BetterEm

_Extension: `pymdownx.betterem`_
_Package: `pymdown-extensions`_
\*Description: Manages combinations of bold and italic (`***text***`, etc.).\*

```md
**_bold and italic_**

***bold and italic***
```

#quote(block: true)[
  *_bold and italic_*

  *_bold and italic_*
]

== Long Dash (—)

_Description: Notes how em-dashes are handled differently by parsers._

No current extension automatically handles the em dash in Markdown. In LaTeX you use `--` for an en dash and `---` for an em dash. The `---` sequence can be confusing in Markdown because it is also used for horizontal rules; however, some parsers such as `markdown-it-py` interpret it contextually. Experiment as needed.

```md
Achiles -- the swifest runner -- was fast, but not as fast as the tortoise.
```

#quote(block: true)[
  Achiles – the swifest runner – was fast, but not as fast as the tortoise.
]

== Additional Syntax

_Description: Highlights extra syntaxes such as callouts and directives._

```md
> [!note] This is a note.
> Used on Docusaurus, Obsidian, GitHub.

::directive{param} Used on MDX, Astro
```

== *Other, Less Common Dialects*

_Description: Summarises less common Markdown dialects and their strengths._

#table(
  columns: 3,
  align: (left, left, left),
  table.header([Dialect], [Highlights], [Package]),
  [*MultiMarkdown*], [Tables, footnotes, citations, extended metadata], [`multimarkdown`],
  [*RMarkdown*], [Executable code (knitr), math, tables], [`rmarkdown` (R)],
  [*kramdown*], [Math, footnotes, block IAL, definition lists], [(Ruby)],
  [*CommonMark Ext.*], [Full GFM support], [`cmarkgfm`],
  [*Ghost / Jekyll*], [“Liquid tags” (`{% include %}`)], [Liquid engine],
  [*MkDocs Material*], [PyMdownX support + Snippets + Tabs + Admonitions], [`mkdocs-material`],
)

#v(1em)
#heading(numbering: none)[Acronyms]

/ HTML: HyperText Markup Language
