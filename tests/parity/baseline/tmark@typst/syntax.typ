#set document(
title: "TMark Syntax",
author: ("Yves Chevallier"),
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
#text(size: 1.8em, weight: "bold")[TMark Syntax]]
#align(center)[
Yves Chevallier]
#v(1.5em)

#block(width: 100%, inset: (x: 2em))[
#align(center)[#text(weight: "bold")[Abstract]]
#v(0.5em)
TMark is the Markdown dialect TeXSmith reads: CommonMark, the extensions authors already know from GitHub and MkDocs, and a small closed set of constructs for print — roles such as `{index}[term]`, containers such as `::: note`, data fences such as `yaml table`. This document walks through the syntax construct by construct, each one shown as source and as the typeset result. It doubles as a test sheet for templates.]
#v(1em)

#outline()
#v(1em)

#ts-callout-style.update("fancy")

= Structure

== Headings

Six heading levels, `#` to `######`. #ts-logo("LaTeX") has fewer sectioning commands (`\section`, `\subsection`, `\subsubsection`, `\paragraph`, `\subparagraph`), so the deepest levels become run-in bold headings.

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

Strong emphasis with `**`, typeset as `\textbf{…}`.

```md
**text** or **t**ex**t**
```

#quote(block: true)[
*text* or *t*ex*t*]

== Italic

Emphasis with `*` or `_`, for terminology or voice.

```md
This _text_ or *text* is italic.
```

#quote(block: true)[
This _text_ or _text_ is italic.]

== Nested emphasis

Bold and italic combine in either spelling.

```md
**_bold and italic_**

***bold and italic***
```

#quote(block: true)[
#ts-lead[_bold and italic_]

_*bold and italic*_]

== Small capitals

In CommonMark `**` and `__` both mean bold. TMark keeps `**` for bold and reads `__` as small capitals.

```md
This is __small capitals__.
```

#quote(block: true)[
This is #smallcaps[small capitals].]

== Strikethrough

Marks text as deleted or obsolete.

```md
We ~~do not~~ want this.
```

#quote(block: true)[
We #strike[do not] want this.]

== Underline

The `{underline}` role underlines text. PyMdownX's `^^text^^` spells the same
node, but only with the `inline.insert` feature enabled; without it the carets
are literal.

```md
{underline}[text]
```

#quote(block: true)[
#underline[text]]

== Highlight

`==text==` highlights a run of text, as a marker would.

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
products.]

== Subscript and superscript

`~…~` lowers, `^…^` raises. Unicode subscripts and superscripts pass through.

```md
H~2~O, E = mc^2^

H₂O, E = mc²
```

#quote(block: true)[
H#sub[2]O, E = mc#super[2]

H₂O, E = mc²]

== Smart punctuation

Straight quotes become typographic quotes, three dots an ellipsis, `–` an en dash and `—` an em dash. A `—` alone on its line is a thematic break, not a dash.

```md
"Smart quotes", ellipses..., en-dash --, em-dash ---

Achilles -- the swiftest runner -- was fast, but not as fast as the tortoise.
```

#quote(block: true)[
"Smart quotes", ellipses..., en-dash –, em-dash —

Achilles – the swiftest runner – was fast, but not as fast as the tortoise.]

== Inline code and code blocks

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
```]

== Links

External links become clickable links in the PDF. A bare URL is linked as it stands.

```md
The German-born physicist [Albert Einstein](https://en.wikipedia.org/wiki/Albert_Einstein) is famous for
his Nobel prize and the theory of relativity: https://en.wikipedia.org/wiki/Theory_of_relativity
```

#quote(block: true)[
The German-born physicist #link("https://en.wikipedia.org/wiki/Albert_Einstein")[Albert Einstein] is famous for
his Nobel prize and the theory of relativity: #link("https://en.wikipedia.org/wiki/Theory_of_relativity")]

== Images

Local or remote images; a remote one is fetched at build time.

```md
![Random Picture](https://picsum.photos/500/200)
```

#quote(block: true)[
#figure(
image("200.jpg"),
caption: [Random Picture],
)]

== Bulleted lists

```md
- First
- Second
    - Subitem
```

#quote(block: true)[
- First
- Second
- Subitem]

== Numbered lists

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
a. Sub-sub-numbered
b. Sub-sub-numbered
+ Sub-numbered]

== Task lists

```md
- [x] Done
- [ ] To do
```

#quote(block: true)[
- #ts-task("done")[Done]
- #ts-task("open")[To do]]

== Definition lists

A term, then its definition on a `:` line.

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
is indented properly.]

== Block quotes

```md
> Quote
```

#quote(block: true)[
Quote]

== Thematic breaks

A `—` on its own line. At the top level of a paged document it turns the page; inside a container it draws a rule.

```md
---
```

#quote(block: true)[
#ts-rule()]

= Blocks

== Tables

Pipe tables for plain 2-D data; a `yaml table` fence for spans, grouped headers and footers (see the `tables` example).

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
)]

== Footnotes

A footnote is a note placed at the bottom of the page.

```md
Text with note[^1].

[^1]: Here is the note.
```

#quote(block: true)[
Text with note#footnote[Here is the note.].]

== Abbreviations

An abbreviation definition expands its first occurrence and lists the acronym in the backmatter.

```md
The HTML standard.

*[HTML]: HyperText Markup Language
```

#quote(block: true)[
The #ts-acr("HTML") standard.]

== Callouts

A `::: kind` container is a callout: note, tip, warning, danger, and the other kinds of the callout palette. Attributes follow the kind. PyMdownX's `!!! note` and `??? warning` spell the same containers.

```md
::: note
This is a note.
:::

::: warning {collapsed=true}
This is a warning.
:::
```

`collapsed=true` creates a collapsible block in #ts-acr("HTML") output only.

#ts-callout(kind: "note")[
This is a note.]

#ts-callout(kind: "warning", collapsed: true)[
This is a warning.]

A title of its own:

```md
::: note {title=Title collapsed=false}
Collapsible content.
:::
```

#quote(block: true)[
#ts-callout(kind: "note", title: [Title], collapsed: false)[
Collapsible content.]]

== Tabs

A `tabs` container holds one `tab` container per pane. Paged output lays the panes one after the other, each under its title.

```md
:::: tabs
::: tab {title=Windows}
Windows is a Microsoft operating system.
:::
::: tab {title=Linux}
Linux is an open-source operating system.
:::
::::
```

#ts-div("tab", title: "Windows")[
Windows is a Microsoft operating system.]

#ts-div("tab", title: "Linux")[
Linux is an open-source operating system.]

== Diagrams

A `mermaid` fence is rendered to a vector image at build time; `image` on the fence makes it a figure, with the attributes an image takes.

````md
```mermaid image width="20%"
graph TD;
  A-->B;
```
````

#quote(block: true)[
#figure(
image("<HASH>.pdf", width: 20%),
)]

== Math

Inline math between `$…$`, display math between `$$…$$`, in #ts-logo("LaTeX") syntax on both backends.

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

#mitex(`\begin{aligned}
\nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
\nabla \cdot \mathbf{B} &= 0 \\
\nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
\nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0
\frac{\partial \mathbf{E}}{\partial t}
\end{aligned}`)]

== Raw passthrough

A `latex raw` fence is written to the #ts-logo("LaTeX") output verbatim; the `{raw latex}(…)` role does the same inside a paragraph. Neither reaches the other backends.

````md
```latex raw
\clearpage
```
````

Inline variant:

```md
Insert... {raw latex}(\clearpage) anywhere in the paragraph.
```

Insert... anywhere in the paragraph.

== Including a file

A fence with `include` takes its content from a file, here a Python program listed with its highlighting.

````md
```python include="hanoi.py"
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

= Inline

== Emoji

Shortcodes and Unicode emoji are typeset with the emoji font of the `fonts.emoji` setting — OpenMoji black unless told otherwise.

```md
:smile:
:heart:
```

#quote(block: true)[
#ts-emoji[😄]
#ts-emoji[❤️]]

```md
😊 🚀 🍕 🎉 🐍 🌍 💻
📚 🎨 👽 👋 🤖 🦄 🧠
```

#quote(block: true)[
#ts-emoji[😊] #ts-emoji[🚀] #ts-emoji[🍕] #ts-emoji[🎉] #ts-emoji[🐍] #ts-emoji[🌍] #ts-emoji[💻]
#ts-emoji[📚] #ts-emoji[🎨] #ts-emoji[👽] #ts-emoji[👋] #ts-emoji[🤖] #ts-emoji[🦄] #ts-emoji[🧠]]

== Keys

`++key+key++` sets keyboard shortcuts as key caps.

```md
++Ctrl+C++
```

#quote(block: true)[
#ts-keys("Ctrl", "C")]

== Progress bars

```markdown
[=25% "Research"]
[=50% "Implementation"]
[=75% "Review"]
[=100% "Launch"]{.thin}
```

#ts-progress(0.25, label: "Research")
#ts-progress(0.5, label: "Implementation")
#ts-progress(0.75, label: "Review")
#ts-progress(1, label: "Launch", thin: true)

== Escaping

A backslash makes any punctuation literal, so a `*`, a `_` or a `{` can be written as it is.

```md
\*not emphasis\*, a literal \{brace\} and a \# that is no heading.
```

#quote(block: true)[
\*not emphasis\*, a literal {brace} and a \# that is no heading.]

= Front matter

A YAML block at the top of the document carries the metadata and the `press` settings: the template, its attributes, the slots, the fonts.

```md
---
title: My document
author: Alice
press:
  template: article
  toc: true
---

# Title
```

#v(1em)
#heading(numbering: none)[Acronyms]

/ HTML: HyperText Markup Language
